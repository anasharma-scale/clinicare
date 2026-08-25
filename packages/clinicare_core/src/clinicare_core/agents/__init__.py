"""Harbor Agent subclasses that patch a vendor CLI's config for this benchmark.

Passed to Harbor as `--agent-import-path clinicare_core.agents.<module>:<Class>`. They live in
an installed package so that import path resolves from any working directory.

Importing this subpackage pulls in `harbor`; the rest of `clinicare_core` does not.
"""
