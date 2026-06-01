from novel_tts.segmentation import split_chapter_text


def test_split_chapter_text_preserves_order_and_bounds():
    text = "第一句。第二句，第三句！第四句？第五句；第六句。"
    parts = split_chapter_text(text, min_chars=6, max_chars=12)
    assert len(parts) >= 3
    assert "".join(parts).replace(" ", "") == text
    assert all(len(p) <= 12 for p in parts)
