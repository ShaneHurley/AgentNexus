import pytest
from agent_core.isolation import DockerRunner


def test_exact_local_content_id_is_an_immutable_pin(tmp_path):
    image = "sha256:" + "a"*64
    assert DockerRunner(image,tmp_path).image == image


@pytest.mark.parametrize("image", ["fixture:latest", "fixture:v1", "sha256:abc", "sha256:"+"A"*64, None, True])
def test_mutable_or_malformed_local_pins_are_rejected(tmp_path,image):
    with pytest.raises(ValueError,match="pinned"):
        DockerRunner(image,tmp_path)
