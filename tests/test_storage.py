from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from span_app.storage import MAX_HABITS, Store


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "span.db")
        self.store.replace_habits(["Read", "Move", "Write"])

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def test_habits_preserve_order_and_can_be_renamed(self) -> None:
        self.assertEqual([h.name for h in self.store.habits()], ["Read", "Move", "Write"])
        self.store.replace_habits(["Read deeply", "Move", "Sleep"])
        self.assertEqual(
            [h.name for h in self.store.habits()],
            ["Read deeply", "Move", "Sleep"],
        )

    def test_toggle_and_daily_counts(self) -> None:
        today = date.today()
        habit = self.store.habits()[0]
        self.assertTrue(self.store.toggle(habit.id, today))
        self.assertEqual(self.store.completed_ids(today), {habit.id})
        self.assertEqual(self.store.daily_counts(today, today), {today: 1})
        self.assertFalse(self.store.toggle(habit.id, today))
        self.assertEqual(self.store.completed_ids(today), set())

    def test_streak_counts_only_perfect_days(self) -> None:
        today = date.today()
        self.store.set_setting("start_date", (today - timedelta(days=3)).isoformat())
        habits = self.store.habits()
        for offset in (1, 0):
            for habit in habits:
                self.store.toggle(habit.id, today - timedelta(days=offset))
        self.assertEqual(self.store.streak(today), 2)

    def test_removed_habit_keeps_history_but_is_not_active(self) -> None:
        today = date.today()
        read, removed, write = self.store.habits()
        self.store.toggle(removed.id, today)
        self.store.save_habits([(read.id, "Read"), (write.id, "Write")])
        self.assertEqual([h.name for h in self.store.habits()], ["Read", "Write"])
        self.assertEqual(self.store.daily_counts(today, today)[today], 1)

    def test_removing_middle_habit_does_not_reassign_identity(self) -> None:
        read, move, write = self.store.habits()
        self.store.save_habits([(read.id, "Read more"), (write.id, "Write")])
        remaining = self.store.habits()
        self.assertEqual([habit.id for habit in remaining], [read.id, write.id])
        self.assertNotIn(move.id, [habit.id for habit in remaining])

    def test_daily_target_is_preserved_after_habit_list_changes(self) -> None:
        today = date.today()
        yesterday = today - timedelta(days=1)
        self.store.toggle(self.store.habits()[0].id, yesterday)
        self.assertEqual(self.store.daily_targets(yesterday, yesterday)[yesterday], 3)
        self.store.save_habits(
            [(habit.id, habit.name) for habit in self.store.habits()[:2]]
        )
        self.assertEqual(self.store.daily_targets(yesterday, yesterday)[yesterday], 3)
        self.assertEqual(self.store.daily_targets(today, today)[today], 2)

    def test_daily_summary_matches_individual_queries(self) -> None:
        today = date.today()
        yesterday = today - timedelta(days=1)
        for habit in self.store.habits()[:2]:
            self.store.toggle(habit.id, yesterday)
        counts, targets = self.store.daily_summary(yesterday, today)
        self.assertEqual(counts, self.store.daily_counts(yesterday, today))
        self.assertEqual(targets, self.store.daily_targets(yesterday, today))

    def test_set_settings_batches_writes(self) -> None:
        self.store.set_settings({"theme": "ocean", "lifespan": 90})
        self.assertEqual(self.store.get_setting("theme"), "ocean")
        self.assertEqual(self.store.get_setting("lifespan"), 90)

    def test_malformed_setting_falls_back_to_default(self) -> None:
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES('theme', 'not json') "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
            )
        self.assertEqual(self.store.get_setting("theme", "forest"), "forest")

    def test_streak_survives_invalid_start_date(self) -> None:
        self.store.set_setting("start_date", "not-a-date")
        self.assertEqual(self.store.streak(date.today()), 0)

    def test_habit_limit_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.store.replace_habits([f"habit {index}" for index in range(MAX_HABITS + 1)])

    def test_store_can_be_closed_and_used_as_context_manager(self) -> None:
        path = Path(self.temp.name) / "second.db"
        with Store(path) as store:
            store.replace_habits(["One"])
            self.assertEqual([habit.name for habit in store.habits()], ["One"])
        store.close()  # idempotent


if __name__ == "__main__":
    unittest.main()
