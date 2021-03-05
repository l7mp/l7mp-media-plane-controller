from rtpeController.commands import Commands

commands = Commands()

def test_ping():
    assert commands.ping() == {"command": "ping"}

def test_offer1():
    desired = {
        "command": "offer",
        "sdp": "test",
        "call-id": "id",
        "from-tag": "tag"
    }
    assert commands.offer("test", "id", "tag") == desired

def test_offer2():
    data = {
        "via-branch": "branch",
        "flags": ["test", "test"],
        "TOS": 12,
        "codec": {
            "example": "example"
        } 
    }
    desired = {
        "command": "offer",
        "sdp": "test",
        "call-id": "id",
        "from-tag": "tag",
        "via-branch": "branch",
        "flags": ["test", "test"],
        "TOS": 12,
        "codec": {
            "example": "example"
        } 
    }
    assert commands.offer("test", "id", "tag", **data) == desired

def test_answer1():
    desired = {
        "command": "answer",
        "sdp": "test",
        "call-id": "id",
        "from-tag": "ftag",
        "to-tag": "ttag"
    }

    assert commands.answer("test", "id", "ftag", "ttag") == desired

def test_answer2():
    data = {
        "via-branch": "branch",
        "flags": ["test", "test"],
        "TOS": 12,
        "codec": {
            "example": "example"
        } 
    }
    desired = {
        "command": "answer",
        "sdp": "test",
        "call-id": "id",
        "from-tag": "ftag",
        "to-tag": "ttag",
        "via-branch": "branch",
        "flags": ["test", "test"],
        "TOS": 12,
        "codec": {
            "example": "example"
        } 
    }
    
    assert commands.answer("test", "id", "ftag", "ttag", **data) == desired

def test_delete():
    data = {
        "to-tag": "ttag",
        "via-branch": "branch",
        "flags": ["fatal"]
    }
    desired = {
        "command": "delete",
        "call-id": "id",
        "from-tag": "ftag",
        "to-tag": "ttag",
        "via-branch": "branch",
        "flags": ["fatal"]
    }

    assert commands.delete("id", "ftag", **data) == desired

def test_list_calls1():
    desired = {
        "command": "list",
        "limit": "32"
    }
    
    assert commands.list_calls() == desired

def test_list_calls2():
    desired = {
        "command": "list",
        "limit": "50"
    }

    assert commands.list_calls(50) == desired

def test_query1():
    desired = {
        "command": "query",
        "call-id": "id"
    }

    assert commands.query("id") == desired

def test_query2():
    data = {
        "from-tag": "ftag",
        "to-tag": "ttag"
    }
    desired = {
        "command": "query",
        "call-id": "id",
        "from-tag": "ftag",
        "to-tag": "ttag"
    }

    assert commands.query("id", **data) == desired

def test_start_recording():
    data = {
        "from-tag": "ftag",
        "to-tag": "ttag",
        "via-branch": "branch"
    }
    desired = {
        "command": "start-recording",
        "call-id": "id",
        "from-tag": "ftag",
        "to-tag": "ttag",
        "via-branch": "branch"
    }

    assert commands.start_recording("id", **data) == desired

def test_stop_recording():
    data = {
        "flags": ["all"]
    }
    desired = {
        "command": "stop-recording",
        "call-id": "id",
        "flags": ["all"]
    }
    
    assert commands.stop_recording("id", **data) == desired

def test_block_dtmf():
    data = {
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }
    desired = {
        "command": "block-dtmf",
        "call-id": "id",
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }

    assert commands.block_dtmf("id", **data) == desired

def test_unblock_dtmf():
    data = {
        "flags": ["all"]
    }
    desired = {
        "command": "unblock-dtmf",
        "call-id": "id",
        "flags": ["all"]
    }

    assert commands.unblock_dtmf("id", **data) == desired

def test_block_media():
    data = {
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }
    desired = {
        "command": "block-media",
        "call-id": "id",
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }

    assert commands.block_media("id", **data) == desired

def test_unblock_media():
    data = {
        "flags": ["all"]
    }
    desired = {
        "command": "unblock-media",
        "call-id": "id",
        "flags": ["all"]
    }

    assert commands.unblock_media("id", **data) == desired

def test_start_forwarding():
    data = {
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }
    desired = {
        "command": "start-forwarding",
        "call-id": "id",
        "from-tag": "ftag",
        "address": "address",
        "label": "label"
    }

    assert commands.start_forwarding("id", **data) == desired

def test_stop_forwarding():
    data = {
        "flags": ["all"]
    }
    desired = {
        "command": "stop-forwarding",
        "call-id": "id",
        "flags": ["all"]
    }

    assert commands.stop_forwarding("id", **data) == desired


def test_play_media():
    data = {
        "from-tag": "ftag",
        "flags": ["all"],
        "db-id": 1,
        "duration": 10
    }
    desired = {
        "command": "play-media",
        "call-id": "id",
        "from-tag": "ftag",
        "flags": ["all"],
        "db-id": 1,
        "duration": 10
    }

    assert commands.play_media("id", **data) == desired

def test_stop_media():
    desired = {
        "command": "stop-media",
        "call-id": "id"
    }
    
    assert commands.stop_media("id") == desired


def test_play_dtmf():
    data = {
        "from-tag": "ftag",
        "flags": ["all"],
        "duration": 1,
        "volume": 1,
        "pause": 1
    }
    desired = {
        "command": "play-dtmf",
        "call-id": "id",
        "code": "1",
        **data
    }

    assert commands.play_dtmf("id", "1", **data) == desired

def test_statistics():
    assert commands.statistics() == {"command": "statistics"}