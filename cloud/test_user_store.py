"""user_store 单元测试（纯标准库；磁盘指到临时目录）。"""
import os
import shutil
import tempfile
import unittest

import user_store


class UserStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="user_store_test_")
        self._orig_dir = user_store.DATA_DIR
        self._orig_path = user_store.STORE_PATH
        user_store.DATA_DIR = self.tmp
        user_store.STORE_PATH = os.path.join(self.tmp, "users.json")

    def tearDown(self):
        user_store.DATA_DIR = self._orig_dir
        user_store.STORE_PATH = self._orig_path
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestCreateAndBind(UserStoreTest):
    def test_token_is_unique_and_unbound(self):
        a = user_store.create_token()
        b = user_store.create_token()
        self.assertNotEqual(a, b)
        self.assertIsNone(user_store.user_for_token(a), "还没绑定就不该有用户")

    def test_bind_creates_user_and_links_token(self):
        token = user_store.create_token()
        user = user_store.bind(token, "小明", "13800000000")
        self.assertIsNotNone(user)
        self.assertEqual(user["nickname"], "小明")
        self.assertEqual(user_store.user_for_token(token)["id"], user["id"])
        self.assertEqual(user_store.user_for_id(user["id"])["nickname"], "小明")

    def test_bind_is_idempotent_for_same_token(self):
        token = user_store.create_token()
        first = user_store.bind(token, "小明")
        second = user_store.bind(token, "小明")
        self.assertEqual(first["id"], second["id"],
                         "同一二维码重复提交不能建两个账号")

    def test_bind_rejects_unknown_token(self):
        self.assertIsNone(user_store.bind("not-a-token", "小明"))

    def test_bind_rejects_empty_or_long_nickname(self):
        token = user_store.create_token()
        self.assertIsNone(user_store.bind(token, ""))
        self.assertIsNone(user_store.bind(token, "长" * 25))

    def test_bind_rejects_bad_phone(self):
        token = user_store.create_token()
        self.assertIsNone(user_store.bind(token, "小明", "not-a-phone"))

    def test_persists_across_loads(self):
        token = user_store.create_token()
        user = user_store.bind(token, "小明")
        # 直接重新读文件（模拟进程重启）
        from_store = user_store.user_for_token(token)
        self.assertEqual(from_store["id"], user["id"])


if __name__ == "__main__":
    unittest.main()
