import unittest
from slugify import slugify


class TestOther(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(slugify("abc"), "abc")


if __name__ == "__main__":
    unittest.main()
