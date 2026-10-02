from cleanup import cleanup_transcript


def test_removes_fillers_and_collapses_immediate_repeats():
    assert cleanup_transcript("Um hello hello, you know world uh!") == "Hello, you know world!"


def test_dictionary_is_whole_word_only_and_umbrella_survives():
    assert cleanup_transcript("use uri and umbrella", {"uri": "URI", "um": "no"}) == "use URI and umbrella"


def test_fixes_punctuation_spacing():
    assert cleanup_transcript("hello , world !") == "hello, world!"


def test_you_know_is_removed_only_when_punctuation_marks_it_as_a_filler():
    assert cleanup_transcript("Well, you know, we should go.") == "Well, we should go."
    assert cleanup_transcript("Do you know the way?") == "Do you know the way?"


def test_filler_removal_preserves_single_punctuation_and_capitalisation():
    assert cleanup_transcript("So, um, the plan") == "So, the plan"
    assert cleanup_transcript("Um, so") == "So"
