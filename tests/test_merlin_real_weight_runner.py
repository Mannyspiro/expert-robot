"""Fail-closed asset checks for real-weight runner."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
SPEC=importlib.util.spec_from_file_location("real_weight",ROOT/"scripts"/"merlin_real_weight_runner.py")
assert SPEC and SPEC.loader
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class RealWeightRunnerTests(unittest.TestCase):
    def test_wrong_digest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"sample.gguf"
            file.write_bytes(b"not a real model")
            with self.assertRaisesRegex(ValueError,"digest mismatch"):
                module.checked(file,"0"*64)

    def test_symlink_asset_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"sample.gguf"
            file.write_bytes(b"data")
            alias=Path(tmp)/"alias.gguf"
            alias.symlink_to(file)
            with self.assertRaisesRegex(ValueError,"regular asset"):
                module.checked(alias,module.digest(file))

    def test_bad_digest_format_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"sample.gguf"
            file.write_bytes(b"data")
            with self.assertRaisesRegex(ValueError,"SHA-256"):
                module.checked(file,"not-a-digest")

    def test_invalid_port_fails_before_process(self):
        with self.assertRaisesRegex(ValueError,"port"):
            module.run(Path("none"),Path("none"),"0"*64,"0"*64,port=80)


if __name__=="__main__":
    unittest.main()
