#!/usr/bin/env python3
"""以标准库运行 unittest 类和现有无参数测试函数。"""

import importlib.util
import inspect
from pathlib import Path
import sys
import unittest


def build_suite() -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("test_") and function.__module__ == module.__name__:
                suite.addTest(unittest.FunctionTestCase(function, description=path.name + "::" + name))
    return suite


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(build_suite())
    sys.exit(0 if result.wasSuccessful() else 1)
