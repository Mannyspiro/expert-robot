"""Source alignment must reject self-consistent packages from different inputs."""
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import zipfile

import security_handoff_smoke as handoff


class PackageSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix="merlin-package-source-tests-")
        cls.addClassCleanup(cls.folder.cleanup)
        cls.root=Path(cls.folder.name)
        cls.builder=handoff._repository_module("portable/build_portable.py")
        cls.verifier=handoff._repository_module("scripts/verify_portable.py")
        cls.package=cls.root/"current.zip"
        cls.builder.build(cls.package)
        cls.prefix=cls.builder.ARCHIVE_ROOT+"/"
        cls.test_file="tests/test_security_review.py"

    def modified_package(self,change):
        with zipfile.ZipFile(self.package) as archive:
            infos={item.filename:item for item in archive.infolist()}
            data={name:archive.read(name) for name in infos}
        manifest_name=self.prefix+"PACKAGE_MANIFEST.json"
        manifest=json.loads(data[manifest_name])
        change(data,manifest,infos)
        for entry in manifest["files"]:
            content=data[self.prefix+entry["path"]]
            entry.update(bytes=len(content),sha256=hashlib.sha256(content).hexdigest())
        data[manifest_name]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
        changed=self.root/"modified.zip"
        with zipfile.ZipFile(changed,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(data):
                item=infos.get(name)
                if item is None:
                    item=zipfile.ZipInfo(name,self.builder.ZIP_TIME)
                    item.create_system=3
                    item.external_attr=(stat.S_IFREG|0o644)<<16
                archive.writestr(item,data[name],compress_type=zipfile.ZIP_DEFLATED)
        self.assertIs(self.verifier.verify(changed)["verified"],True)
        return changed

    def test_current_source_package_passes(self):
        self.assertIs(handoff.verify_package_source(self.package),True)

    def test_self_consistent_stale_payload_rejected_before_producer(self):
        def stale(data,manifest,infos):
            data[self.prefix+self.test_file]+=b"\n# Different source revision.\n"
        package=self.modified_package(stale)
        with mock.patch.object(handoff,"bounded_run",side_effect=AssertionError("producer must not run")) as child:
            with self.assertRaisesRegex(ValueError,"payload differs.*tests/test_security_review"):
                handoff.run(self.root,package)
            child.assert_not_called()

    def test_matching_bytes_at_an_arbitrary_manifest_origin_are_not_authority(self):
        outside=self.root/"not-a-builder-source.py"
        with zipfile.ZipFile(self.package) as archive:
            outside.write_bytes(archive.read(self.prefix+self.test_file))
        def changed_origin(data,manifest,infos):
            next(entry for entry in manifest["files"] if entry["path"]==self.test_file)["source"]=str(outside)
        package=self.modified_package(changed_origin)
        with self.assertRaisesRegex(ValueError,"origin differs"):
            handoff.verify_package_source(package)

    def test_self_consistent_inventory_change_is_rejected(self):
        def removed(data,manifest,infos):
            del data[self.prefix+self.test_file]
            manifest["files"]=[entry for entry in manifest["files"] if entry["path"]!=self.test_file]
        def added(data,manifest,infos):
            data[self.prefix+"unlisted-source.txt"]=b"not in canonical builder mapping\n"
            manifest["files"].append({"path":"unlisted-source.txt","mode":"0644","source":"unlisted-source.txt"})
        for change in (removed,added):
            with self.subTest(change=change.__name__):
                package=self.modified_package(change)
                with self.assertRaisesRegex(ValueError,"inventory differs"):
                    handoff.verify_package_source(package)

    def test_source_only_contract_and_fixed_modes_are_required(self):
        for included in (True,0):
            with self.subTest(included=repr(included)):
                def changed_native(data,manifest,infos):
                    manifest["native_protocol"]["included"]=included
                package=self.modified_package(changed_native)
                with self.assertRaisesRegex(ValueError,"source-only package contract"):
                    handoff.verify_package_source(package)
        def changed_mode(data,manifest,infos):
            next(entry for entry in manifest["files"] if entry["path"]==self.test_file)["mode"]="0755"
            infos[self.prefix+self.test_file].external_attr=(stat.S_IFREG|0o755)<<16
        package=self.modified_package(changed_mode)
        with self.assertRaisesRegex(ValueError,"mode differs"):
            handoff.verify_package_source(package)


if __name__=="__main__":
    unittest.main()
