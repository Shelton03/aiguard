"""Tests for symbol filtering and text cleaning functionality."""
import pytest
from cli.reporting import clean_report_text


class TestSymbolFiltering:
    """Test Unicode artifact cleaning."""

    def test_smart_quotes_double_to_straight(self):
        """Test conversion of double smart quotes to straight quotes."""
        assert clean_report_text('"hello"', 'metadata') == '"hello"'
        assert clean_report_text('"world"', 'metadata') == '"world"'

    def test_smart_quotes_single_to_straight(self):
        """Test conversion of single smart quotes to straight quotes."""
        assert clean_report_text("'hello'", 'metadata') == "'hello'"
        assert clean_report_text("'world'", 'metadata') == "'world'"

    def test_emdash_to_hyphen(self):
        """Test conversion of em-dash to hyphen."""
        assert clean_report_text('hello—world', 'metadata') == 'hello-world'

    def test_endedash_to_hyphen(self):
        """Test conversion of en-dash to hyphen."""
        assert clean_report_text('hello–world', 'metadata') == 'hello-world'

    def test_remove_zero_width_space(self):
        """Test removal of zero-width space character."""
        assert clean_report_text('hello\u200bworld', 'metadata') == 'helloworld'

    def test_remove_zero_width_nonjoiner(self):
        """Test removal of zero-width non-joiner."""
        assert clean_report_text('hello\u200cworld', 'metadata') == 'helloworld'

    def test_remove_zero_width_joiner(self):
        """Test removal of zero-width joiner."""
        assert clean_report_text('hello\u200dworld', 'metadata') == 'helloworld'

    def test_remove_bom(self):
        """Test removal of BOM character."""
        assert clean_report_text('\ufeffhello', 'metadata') == 'hello'

    def test_convert_nbsp_to_space(self):
        """Test conversion of non-breaking space to regular space."""
        assert clean_report_text('hello\u00a0world', 'metadata') == 'hello world'

    def test_metadata_single_line_normalization(self):
        """Test that metadata fields are normalized to single line."""
        assert clean_report_text('hello\n  world', 'metadata') == 'hello world'
        assert clean_report_text('hello\t\tworld', 'metadata') == 'hello world'
        assert clean_report_text('hello\n\nworld', 'metadata') == 'hello world'

    def test_rationale_whitespace_normalization(self):
        """Test that rationale fields normalize whitespace but keep paragraphs."""
        result = clean_report_text('hello  world', 'rationale')
        assert result == 'hello world'
        
        result = clean_report_text('hello\n\nworld', 'rationale')
        assert result == 'hello\n\nworld'

    def test_prompt_preserves_structure(self):
        """Test that prompt fields preserve line breaks."""
        text = 'line1\nline2\nline3'
        result = clean_report_text(text, 'prompt')
        assert result == text

    def test_response_preserves_structure(self):
        """Test that response fields preserve paragraph breaks."""
        text = 'paragraph1\n\nparagraph2'
        result = clean_report_text(text, 'response')
        assert result == text

    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        assert clean_report_text('', 'metadata') == ''
        assert clean_report_text(None, 'metadata') is None

    def test_whitespace_only(self):
        """Test handling of whitespace-only strings."""
        assert clean_report_text('   ', 'metadata') == ''
        assert clean_report_text('\n\n', 'metadata') == ''

    def test_multilingual_text_cleaning(self):
        """Test that cleaning works for non-English text."""
        french = 'Bonjour \u2014 le monde'
        assert clean_report_text(french, 'metadata') == 'Bonjour - le monde'
        
        spanish = 'Hola\x80mundo'
        result = clean_report_text(spanish, 'metadata')
        assert 'Hola' in result and 'mundo' in result

    def test_mixed_artifacts(self):
        """Test cleaning of multiple artifact types in one string."""
        text = '"Hello"\u2014world\u200btest'
        result = clean_report_text(text, 'metadata')
        assert result == '"Hello"-worldtest'

    def test_complex_rationale(self):
        """Test cleaning of complex rationale text."""
        text = '''This is a rationale with "smart quotes" and an em-dash—
        multiple spaces   and tabs		between words.
        
        And a paragraph break.'''
        result = clean_report_text(text, 'rationale')
        assert '"smart quotes"' in result
        assert 'em-dash-' in result
        assert '   ' not in result  # No multiple spaces

    def test_case_preservation(self):
        """Test that cleaning preserves case."""
        assert clean_report_text('HELLO', 'metadata') == 'HELLO'
        assert clean_report_text('hello', 'metadata') == 'hello'
        assert clean_report_text('HeLLo WoRLd', 'metadata') == 'HeLLo WoRLd'


class TestFieldSpecificCleaning:
    """Test field-specific cleaning rules."""

    def test_metadata_strict_normalization(self):
        """Test metadata field strict normalization."""
        text = '  Hello   World  \n'
        result = clean_report_text(text, 'metadata')
        assert result == 'Hello World'
        assert result == ' '.join(result.split())

    def test_explanation_normalization(self):
        """Test explanation field normalization."""
        text = 'Line 1\n  \nLine 2'
        result = clean_report_text(text, 'explanation')
        assert '\n\n' in result or '\n' in result

    def test_all_field_types(self):
        """Test all supported field types."""
        text = 'test\x80text'
        
        for field_type in ['prompt', 'response', 'rationale', 'explanation', 'metadata']:
            result = clean_report_text(text, field_type)
            assert result is not None
            assert isinstance(result, str)
