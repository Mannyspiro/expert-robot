"""Small CPU fixtures for paging boundaries; no trained checkpoint is loaded.

Run with the profile's pinned installed Python/Torch closure. Full learned-model
acceptance is a separate frozen protocol and must acquire the shared run lock.
"""
import gc
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import weakref

import torch
from accelerate.hooks import AlignDevicesHook, add_hook_to_module

import parallax_virtual_memory as virtual

torch.set_num_threads(2)


class BudgetTests(unittest.TestCase):
    def test_public_preflight_needs_no_torch_import_or_payload_access(self):
        directory = str(Path(__file__).resolve().parent)
        code = ("import sys; sys.path.insert(0," + repr(directory) + "); "
                "import parallax_virtual_memory as m; "
                "assert 'torch' not in sys.modules; "
                "assert m.validate_budget(32*1024**2,4096)==26214400; "
                "assert 'torch' not in sys.modules")
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_budget_boundary_and_invalid_controls_refuse_before_model_load(self):
        self.assertEqual(virtual.validate_budget(26214400, 4096), 26214400)
        invalid = [(26214399, 4096), (0, 1), (True, 1), (2**28, 1),
                   (32 * 1024**2, True), (32 * 1024**2, 0), (32 * 1024**2, 8193)]
        with mock.patch.object(virtual.direct, "load_direct", side_effect=AssertionError("unexpected model access")) as load:
            for budget, rows in invalid:
                with self.subTest(budget=budget, rows=rows), self.assertRaises(ValueError):
                    virtual.load_ram_managed(Path("missing-checkpoint"), Path("missing-index"), budget, rows)
        load.assert_not_called()


class PagingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="merlin-virtual-ram-fixture-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.weight = (torch.arange(11 * 8, dtype=torch.float32).reshape(11, 8) - 40) / 16
        self.weight = self.weight.to(torch.bfloat16)
        data = self.weight.view(torch.uint16).numpy().tobytes()
        header = json.dumps({virtual.TIED_SOURCE: {"dtype": "BF16", "shape": [11, 8],
                                                   "data_offsets": [0, len(data)]}}, separators=(",", ":")).encode()
        self.content = struct.pack("<Q", len(header)) + header + data
        self.path = self.root / "fixture.safetensors"
        self.path.write_bytes(self.content)
        self.spec = dict(rows=11, columns=8, data_offset=0, file_bytes=len(self.content),
                         file_sha256=hashlib.sha256(self.content).hexdigest(),
                         managed_bytes=512, tile_rows=4, max_positions=8)

    def manager(self, **overrides):
        manager = virtual._PagedRows(self.path, **{**self.spec, **overrides})
        self.addCleanup(manager.close)
        manager._bind_verified_safetensors_matrix(virtual.TIED_SOURCE)
        return manager

    def test_selected_embedding_rows_match_dense_with_duplicates_and_no_full_load(self):
        manager = self.manager()
        ids = torch.tensor([[10, 0, 10, 3, 0]], dtype=torch.long)
        with torch.inference_mode():
            result = manager.embedding(ids)
        expected = torch.nn.functional.embedding(ids, self.weight.float())
        self.assertTrue(torch.equal(result, expected))
        state = manager.snapshot()
        self.assertEqual(state["embedding_rows_read"], 3)
        self.assertEqual(state["embedding_positions_served"], 5)
        self.assertEqual(state["weight_bytes_read"], 3 * 8 * 2)
        self.assertEqual(state["managed_current_bytes"], 0)
        self.assertEqual(state["tiles_loaded"], state["tiles_released"])
        self.assertLessEqual(state["managed_peak_bytes"], 512)

    def test_tiled_projection_matches_dense_including_final_short_tile_and_releases_objects(self):
        manager = self.manager()
        hidden = (torch.arange(24, dtype=torch.float32).reshape(1, 3, 8) - 12) / 8
        expected = torch.nn.functional.linear(hidden, self.weight.float())
        actual_shapes, refs = [], []
        original = torch.nn.functional.linear

        def observed(input, weight):
            actual_shapes.append(list(weight.shape))
            self.assertEqual(manager.snapshot()["managed_current_bytes"], weight.numel() * 6)
            result = original(input, weight)
            refs.extend([weakref.ref(weight), weakref.ref(result)])
            return result

        with torch.inference_mode(), mock.patch.object(torch.nn.functional, "linear", observed):
            result = manager.project(hidden)
        self.assertTrue(torch.equal(result, expected))
        self.assertEqual(actual_shapes, [[4, 8], [4, 8], [3, 8]])
        gc.collect()
        self.assertTrue(all(ref() is None for ref in refs), "a tile escaped after copying its result")
        state = manager.snapshot()
        self.assertEqual(state["projection_tiles"], 3)
        self.assertEqual(state["weight_bytes_read"], 11 * 8 * 2)
        self.assertEqual(state["component_peak_bytes"]["fp32_weights"], 4 * 8 * 4)
        self.assertEqual(state["component_peak_bytes"]["projection_result"], 3 * 4 * 4)
        self.assertEqual(state["managed_current_bytes"], 0)
        self.assertEqual(state["tiles_loaded"], state["tiles_released"])
        self.assertLessEqual(state["managed_peak_bytes"], state["managed_budget_bytes"])

    def test_wrong_hash_wrong_size_and_symlink_sources_fail_before_use(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.manager(file_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "exact size"):
            self.manager(file_bytes=len(self.content) + 1)
        actual = self.path.with_name("original.safetensors")
        self.path.rename(actual)
        self.path.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "nonsymlink"):
            self.manager()

    def test_header_layout_comes_from_hashed_descriptor_and_rejects_wrong_tensor(self):
        manager = virtual._PagedRows(self.path, **self.spec)
        self.addCleanup(manager.close)
        with self.assertRaises(KeyError):
            manager._bind_verified_safetensors_matrix("invented.weight")
        self.assertEqual(manager.snapshot()["weight_bytes_read"], 0)
        manager._bind_verified_safetensors_matrix(virtual.TIED_SOURCE)
        self.assertGreater(manager.data_offset, 8)
        # Same-size mutation after full hashing must fail before a tile is read.
        changed = bytearray(self.content); changed[-1] ^= 1
        self.path.write_bytes(changed)
        with torch.inference_mode(), self.assertRaisesRegex(ValueError, "changed"):
            manager.embedding(torch.tensor([[0]], dtype=torch.long))
        self.assertEqual(manager.snapshot()["weight_bytes_read"], 0)

    def test_invalid_dtype_device_shape_ids_and_grad_mode_do_not_page(self):
        manager = self.manager()
        with self.assertRaisesRegex(ValueError, "inference/no-grad"):
            manager.embedding(torch.tensor([[0]], dtype=torch.long))
        ids = [torch.tensor([[0.0]]), torch.tensor([[-1]], dtype=torch.long),
               torch.tensor([[11]], dtype=torch.long), torch.zeros((2, 1), dtype=torch.long),
               torch.zeros((1, 9), dtype=torch.long), torch.empty((1, 1), dtype=torch.long, device="meta")]
        hidden = [torch.zeros((1, 1, 8), dtype=torch.bfloat16), torch.zeros((1, 1, 9)),
                  torch.zeros((1, 3, 16))[:, :, ::2]]
        with torch.inference_mode():
            for item in ids:
                with self.subTest(kind="ids", shape=list(item.shape)), self.assertRaises(ValueError):
                    manager.embedding(item)
            for item in hidden:
                with self.subTest(kind="hidden", shape=list(item.shape)), self.assertRaises(ValueError):
                    manager.project(item)
        self.assertEqual(manager.snapshot()["weight_bytes_read"], 0)

    def test_operation_failure_releases_buffers_and_propagates_without_returning_partial_logits(self):
        manager = self.manager()
        with torch.inference_mode(), mock.patch.object(torch.nn.functional, "linear", side_effect=RuntimeError("fixture kernel failure")):
            with self.assertRaisesRegex(RuntimeError, "fixture kernel failure"):
                manager.project(torch.ones((1, 1, 8)))
        state = manager.snapshot()
        self.assertEqual(state["managed_current_bytes"], 0)
        self.assertEqual(state["tiles_loaded"], state["tiles_released"])
        self.assertEqual(manager._buffers, {})
        manager.check_source()

    def test_truncated_tile_failure_releases_raw_buffer(self):
        manager = self.manager()
        with torch.inference_mode(), mock.patch.object(manager._source, "readinto", return_value=0):
            with self.assertRaisesRegex(ValueError, "truncated virtual tensor tile"):
                manager.embedding(torch.tensor([[0]], dtype=torch.long))
        self.assertEqual(manager.snapshot()["managed_current_bytes"], 0)
        self.assertEqual(manager._buffers, {})

    def test_close_is_idempotent_snapshot_survives_and_reuse_refuses(self):
        manager = self.manager()
        manager.close(); manager.close()
        self.assertTrue(manager.snapshot()["closed"])
        with torch.inference_mode(), self.assertRaisesRegex(ValueError, "closed"):
            manager.embedding(torch.tensor([[0]], dtype=torch.long))
        with torch.inference_mode(), self.assertRaisesRegex(ValueError, "closed"):
            manager.project(torch.zeros((1, 1, 8)))

    def test_overlapping_operation_and_active_close_refuse(self):
        manager = self.manager()
        with manager._operation(), torch.inference_mode():
            with self.assertRaisesRegex(ValueError, "one virtual tensor operation"):
                manager.project(torch.zeros((1, 1, 8)))
            with self.assertRaisesRegex(ValueError, "cannot close"):
                manager.close()
        self.assertFalse(manager.snapshot()["closed"])
        self.assertEqual(manager.snapshot()["weight_bytes_read"], 0)

    def test_constructor_failure_closes_its_descriptor(self):
        observed = []

        def fail(instance, *_):
            observed.append(instance)
            raise RuntimeError("fixture verification failure")

        with mock.patch.object(virtual._PagedRows, "_verify_complete_source", fail):
            with self.assertRaisesRegex(RuntimeError, "fixture verification failure"):
                self.manager()
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0]._closed)
        self.assertTrue(observed[0]._source.closed)


class HookTests(unittest.TestCase):
    def test_meta_hook_detaches_without_loading_weight_and_cpu_origin_refuses(self):
        class ForbiddenWeights(dict):
            def __getitem__(self, key):
                raise AssertionError("full matrix must never be retrieved")

            def get(self, key, default=None):
                raise AssertionError("full matrix must never be retrieved")

        empty = torch.nn.Linear(8, 11, bias=False, device="meta")
        add_hook_to_module(empty, AlignDevicesHook(execution_device=torch.device("cpu"), offload=True,
                                                  weights_map=ForbiddenWeights()))
        virtual._remove_empty_hook(empty)
        self.assertEqual(empty.weight.device.type, "meta")
        self.assertFalse(hasattr(empty, "_hf_hook"))

        original_cpu = torch.nn.Linear(8, 11, bias=False, device="cpu")
        add_hook_to_module(original_cpu, AlignDevicesHook(execution_device=torch.device("cpu"), offload=True,
                                                         weights_map=ForbiddenWeights()))
        with self.assertRaisesRegex(ValueError, "unchanged empty-weight"):
            virtual._remove_empty_hook(original_cpu)
        self.assertTrue(hasattr(original_cpu, "_hf_hook"))
        self.assertEqual(original_cpu.weight.device.type, "meta")


if __name__ == "__main__":
    unittest.main()
