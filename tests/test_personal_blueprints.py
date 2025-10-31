from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from db import database
from db.models import Blueprint
from esi import personal_blueprints


class PersonalBlueprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.private_dir = os.path.join(self.tempdir.name, "private")

        os.environ["EVE_PRIVATE_DATABASE_FOLDER"] = self.private_dir
        database.PRIVATE_DATA_FOLDER = self.private_dir
        database._private_engines = {}
        database._PrivateSessions = {}

        self.owner_id = 4321
        self.char_id = 987654
        database.initialize_private_database(self.owner_id)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _fetch_rows(self) -> list[Blueprint]:
        session = database.get_private_session(self.owner_id)
        try:
            return session.query(Blueprint).filter_by(character_id=self.char_id).all()
        finally:
            session.close()

    def test_store_blueprints_replaces_existing_rows(self) -> None:
        session = database.get_private_session(self.owner_id)
        session.add(
            Blueprint(
                item_id=1,
                character_id=self.char_id,
                type_id=1001,
                material_efficiency=2,
                time_efficiency=4,
                runs=1,
                quantity=1,
                location_id=500,
                location_flag="Old",
            )
        )
        session.commit()
        session.close()

        payload = [
            {
                "item_id": 42,
                "type_id": 2002,
                "material_efficiency": 10,
                "time_efficiency": 20,
                "runs": 8,
                "quantity": 3,
                "location_id": 123,
                "location_flag": "CorpHangar",
            }
        ]

        personal_blueprints.store_blueprints(self.owner_id, self.char_id, payload)

        rows = self._fetch_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.item_id, 42)
        self.assertEqual(row.type_id, 2002)
        self.assertEqual(row.material_efficiency, 10)
        self.assertEqual(row.time_efficiency, 20)
        self.assertEqual(row.runs, 8)
        self.assertEqual(row.quantity, 3)
        self.assertEqual(row.location_id, 123)
        self.assertEqual(row.location_flag, "CorpHangar")

    def test_fetch_all_blueprints_persists_results(self) -> None:
        blueprint_payload = [
            {
                "item_id": 77,
                "type_id": 3003,
                "material_efficiency": 5,
                "time_efficiency": 6,
                "runs": 12,
                "quantity": 1,
                "location_id": 321,
                "location_flag": "Hangar",
            }
        ]

        with mock.patch.object(
            personal_blueprints, "get_token", return_value={self.char_id: {"access_token": "abc"}}
        ), mock.patch.object(
            personal_blueprints, "fetch_blueprints", return_value=blueprint_payload
        ) as fetch_mock:
            personal_blueprints.fetch_all_blueprints(self.owner_id)
            fetch_mock.assert_called_once_with(self.char_id, "abc")

        rows = self._fetch_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].item_id, 77)
        self.assertEqual(rows[0].type_id, 3003)


if __name__ == "__main__":
    unittest.main()
