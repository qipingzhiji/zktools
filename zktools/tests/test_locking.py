from contextlib import nested
import unittest
import mock


class TestLocking(unittest.TestCase):
    def makeOne(self, *args, **kwargs):
        from zktools.locking import ZkLock
        return ZkLock(*args, **kwargs)

    def test_lock_success(self):
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0001'
        )
        mock_conn.get_children.return_value = ['lock0001']

        lock = self.makeOne(mock_conn, 'lock')
        with mock.patch('zktools.connection.zookeeper', mock_zc):
            result = lock.acquire()
            self.assertEqual(result, True)
            result = lock.release()
            self.assertEqual(result, True)

    def test_lock_disconnect_issue(self):
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0001',
            '/ZktoolsLocks/lock/lock0002'
        )
        mock_conn.get_children.side_effect = sequence(
            [], ['lock0002']
        )

        lock = self.makeOne(mock_conn, 'lock')
        with mock.patch('zktools.connection.zookeeper', mock_zc):
            result = lock.acquire()
            self.assertEqual(result, True)
            result = lock.release()
            self.assertEqual(result, True)

    def test_lock_has_lock(self):
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0001',
            '/ZktoolsLocks/lock/lock0002'
        )
        mock_conn.get_children.side_effect = sequence(
            ['lock0001'], ['lock0001']
        )

        lock = self.makeOne(mock_conn, 'lock')
        with mock.patch('zktools.connection.zookeeper', mock_zc):
            self.assertEqual(lock.acquire(), True)
            self.assertEqual(lock.has_lock(), True)
            self.assertEqual(lock.release(), True)

    def test_lock_wait(self):
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0002'
        )
        mock_conn.get_children.side_effect = sequence(
            ['lock0001', 'lock0002'], ['lock0002']
        )

        lock = self.makeOne(mock_conn, 'lock')

        def release_wait(prior_node, func):
            func(0, 0, 0, 0)

        mock_conn.exists.side_effect = release_wait

        with mock.patch('zktools.connection.zookeeper', mock_zc):
            self.assertEqual(lock.acquire(), True)
            self.assertEqual(lock.release(), True)
            self.assertEqual(len(mock_conn.method_calls), 7)

    def test_no_blocking(self):
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0002'
        )
        mock_conn.get_children.side_effect = sequence(
            ['lock0001', 'lock0002'],
        )

        lock = self.makeOne(mock_conn, 'lock')

        def release_wait(prior_node, func):
            func(0, 0, 0, 0)

        mock_conn.exists.side_effect = release_wait

        with mock.patch('zktools.connection.zookeeper', mock_zc):
            self.assertEqual(lock.acquire(timeout=0), False)
            self.assertEqual(len(mock_conn.method_calls), 4)

    def test_lock_revoked_upon_acquiring(self):
        """Test that we handle it if we acquired the lock, but then
        the node was deleted"""
        mock_conn = mock.Mock()
        mock_conn.cv = mock.Mock()
        mock_zc = mock.Mock()
        mock_conn.create.side_effect = sequence(
            '/ZktoolsLocks',
            '/ZktoolsLocks/lock',
            '/ZktoolsLocks/lock/lock0001',
            '/ZktoolsLocks/lock/lock0002'
        )
        mock_conn.get_children.side_effect = sequence(
            ['lock0001'], ['lock0002']
        )

        # We can't fake the zookeeper exception apparently
        import zookeeper
        mock_conn.set.side_effect = sequence(
            zookeeper.NoNodeException(),
            None
        )

        lock = self.makeOne(mock_conn, 'lock')

        def release_wait(prior_node, func):
            func(0, 0, 0, 0)

        mock_conn.exists.side_effect = release_wait

        with mock.patch('zktools.connection.zookeeper', mock_zc):
            self.assertEqual(lock.acquire(), True)
            self.assertEqual(len(mock_conn.method_calls), 4)


def sequence(*args):
    orig_values = args
    values = list(reversed(args))

    def return_value(*args):  # pragma: nocover
        try:
            val = values.pop()
            if isinstance(val, Exception):
                raise val
            else:
                return val
        except IndexError:
            print orig_values
            raise
    return return_value