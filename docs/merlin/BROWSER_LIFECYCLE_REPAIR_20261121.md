# Merlin browser supervisor lifecycle repair

This candidate addresses the stop/cleanup mechanism identified after OCI inspection **44960251285**. It does not remove the retained host socket or activate a service.

## Behavior

`SIGTERM` and `SIGINT` unwind the supervisor, terminate any launched worker process group, reap its direct child, and remove only the socket inode created by that supervisor. Startup refuses every retained path. Replacement sockets, files and symlinks remain intact. A stop during socket binding is deferred until its inode is recorded. During child spawn, only the parent handler defers delivery, so a launched executable does not inherit blocked stop signals. Repeated stop signals cannot interrupt cleanup.

The directory is a root-owned non-writable namespace boundary. The inode check followed by unlink is not an atomic compare-unlink operation against another privileged writer. SIGKILL and crashes still require explicit retained-state reconciliation.

## Actual local validation

- **41 existing browser tests passed** against final source.
- **12 new signal/process/ownership controls passed**, using actual OS signals, subprocesses, pipes and reaping with a clearly labeled file-backed listener fixture.
- **5 selected new controls failed against exact original source.** Direct fixture observations retain original SIGTERM exit -15 and leftover path; the candidate exits0 and removes its own path. Original SIGINT cleanup deleted a replaced fixture inode; corrected cleanup preserved its foreign contents.
- Independent review caught a blocked-child-signal-mask defect in the initial candidate. A real-child regression fails on that preserved intermediate source and passes on the final source. A second real-process control injects SIGTERM inside the Popen return window and checks direct-child reaping.
- **13 real Unix-socket cases are prepared but unqualified locally.** The first attempt was blocked by the execution environment returning EPERM when creating AF_UNIX sockets: 3 passes,9 failures,1 error. No skipped case is counted as success, and the original output is retained.

Run the full three-suite acceptance with **66 tests, no skips** on the intended native fixture lane:

```sh
PYTHONPATH=python python -m unittest discover -s tests -p 'test_public_browser.py' -v
PYTHONPATH=python python -m unittest discover -s tests -p 'test_browser_service_lifecycle_controls.py' -v
PYTHONPATH=python python -m unittest discover -s tests -p 'test_browser_service_lifecycle.py' -v
```

The native suite uses a private temporary directory and root-admission/chown test doubles to execute as the runner user. It does not open public URLs or alter service/provider state. This is a source-level test gate, not production service qualification.

`evidence/result.json` binds the final source/tests and scoped outcomes. Original failures, the initial frame, baseline source, the rejected intermediate signal-mask approach and final patch remain in `evidence/`.
