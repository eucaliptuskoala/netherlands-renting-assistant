import pytest

from bot import (
    BTN_ACCEPT,
    BTN_ACCEPTED,
    BTN_CHANGE_SETTINGS,
    BTN_COVER_LETTER,
    BTN_EDIT_BIO,
    BTN_MENU,
    BTN_MOVE_REJECTED,
    BTN_NEW,
    BTN_NEXT,
    BTN_REJECT,
    BTN_REJECTED,
    BTN_SETTINGS,
    browse_accepted_keyboard,
    format_listing,
    new_listing_keyboard,
    routing_keyboard,
    settings_keyboard,
)


@pytest.mark.unit
def test_format_listing(sample_listing):
    formatted = format_listing(sample_listing)

    assert '🆕 Kerkstraat 42 (📍 Eindhoven)' in formatted
    assert '💰 €1150 / 58 m²' in formatted
    assert '🔗 https://www.funda.nl/' in formatted


@pytest.mark.unit
def test_routing_keyboard():
    markup = routing_keyboard()
    button_texts = [btn.text for row in markup.keyboard for btn in row]

    assert BTN_NEW in button_texts
    assert BTN_ACCEPTED in button_texts
    assert BTN_REJECTED in button_texts
    assert BTN_SETTINGS in button_texts


@pytest.mark.unit
def test_settings_keyboard():
    markup = settings_keyboard()
    button_texts = [btn.text for row in markup.keyboard for btn in row]

    assert BTN_CHANGE_SETTINGS in button_texts
    assert BTN_EDIT_BIO in button_texts


@pytest.mark.unit
def test_new_listing_keyboard():
    markup = new_listing_keyboard()
    button_texts = [btn.text for row in markup.keyboard for btn in row]

    assert BTN_ACCEPT in button_texts
    assert BTN_REJECT in button_texts
    assert BTN_COVER_LETTER in button_texts
    assert BTN_MENU in button_texts


@pytest.mark.unit
def test_browse_accepted_keyboard():
    markup = browse_accepted_keyboard()
    button_texts = [btn.text for row in markup.keyboard for btn in row]

    assert BTN_NEXT in button_texts
    assert BTN_MOVE_REJECTED in button_texts
    assert BTN_COVER_LETTER in button_texts
    assert BTN_MENU in button_texts
