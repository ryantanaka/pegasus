import json
from tempfile import NamedTemporaryFile, TemporaryFile

import pytest

import Pegasus
from Pegasus import yaml
from Pegasus.api.replica_catalog import ReplicaCatalog, _ReplicaCatalogEntry
from Pegasus.replica_catalog import _to_rc, dump, dumps, load, loads


@pytest.fixture(scope="module")
def rc_as_dict():
    return {
        "pegasus": "5.0",
        "replicas": [
            {"lfn": "a", "pfn": "/a", "site": "local", "regex": True},
            {"lfn": "b", "pfn": "/b", "site": "local"},
            {
                "lfn": "c",
                "pfn": "/c",
                "site": "local",
                "checksum": {"type": "sha256", "value": "abc123"},
            },
        ],
    }


def test_to_rc(rc_as_dict):

    expected = ReplicaCatalog()
    expected.add_replica("local", "a", "/a", regex=True)
    expected.add_replica("local", "b", "/b")
    expected.add_replica(
        "local", "c", "/c", checksum_type="sha256", checksum_value="abc123"
    )

    result = _to_rc(rc_as_dict)

    assert result.replicas == expected.replicas


def test_load(mocker, rc_as_dict):
    mocker.patch("Pegasus.yaml.load", return_value=rc_as_dict)
    with TemporaryFile() as f:
        rc = load(f)
        Pegasus.yaml.load.assert_called_once_with(f)

        assert len(rc.replicas) == 3
        assert _ReplicaCatalogEntry("local", "a", "/a", regex=True) in rc.replicas
        assert _ReplicaCatalogEntry("local", "b", "/b") in rc.replicas
        assert _ReplicaCatalogEntry(
            "local", "c", "/c", checksum_type="sha256", checksum_value="abc123"
        )


def test_loads(mocker, rc_as_dict):
    mocker.patch("Pegasus.yaml.load", return_value=rc_as_dict)
    rc = loads(json.dumps(rc_as_dict))

    assert len(rc.replicas) == 3
    assert _ReplicaCatalogEntry("local", "a", "/a", regex=True) in rc.replicas
    assert _ReplicaCatalogEntry("local", "b", "/b") in rc.replicas
    assert _ReplicaCatalogEntry(
        "local", "c", "/c", checksum_type="sha256", checksum_value="abc123"
    )


def test_dump(mocker):
    mocker.patch("Pegasus.api.writable.Writable.write")
    rc = ReplicaCatalog()
    with NamedTemporaryFile(mode="w") as f:
        dump(rc, f, _format="yml")
        Pegasus.api.writable.Writable.write.assert_called_once_with(f, _format="yml")


def test_dumps(rc_as_dict):
    rc = ReplicaCatalog()
    rc.add_replica("local", "a", "/a", regex=True)
    rc.add_replica("local", "b", "/b")
    rc.add_replica("local", "c", "/c", checksum_type="sha256", checksum_value="abc123")

    rc_as_dict["replicas"] = sorted(rc_as_dict["replicas"], key=lambda r: r["lfn"])

    result = yaml.load(dumps(rc))
    result["replicas"] = sorted(result["replicas"], key=lambda r: r["lfn"])

    assert result["replicas"] == rc_as_dict["replicas"]
