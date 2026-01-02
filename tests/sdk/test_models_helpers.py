"""
Unit tests for helper models in src.models.

Tests cover:
- MbrDelta and MbrDeltaSign
- RegistryParameters
- MetadataExistence
- Pagination
- PaginatedMetadata
"""

import pytest

from smart_contracts import constants as const
from smart_contracts.asa_metadata_registry import enums
from src.models import (
    MbrDelta,
    MbrDeltaSign,
    MetadataExistence,
    PaginatedMetadata,
    Pagination,
    RegistryParameters,
    _coerce_bytes,
    _is_nonzero_32,
    _set_bit,
)


class TestMbrDeltaSign:
    """Tests for MbrDeltaSign enum."""

    def test_values(self) -> None:
        """Test enum values match expected constants."""
        assert MbrDeltaSign.NULL == enums.MBR_DELTA_NULL
        assert MbrDeltaSign.POS == enums.MBR_DELTA_POS
        assert MbrDeltaSign.NEG == enums.MBR_DELTA_NEG

    def test_int_values(self) -> None:
        """Test actual integer values."""
        assert MbrDeltaSign.NULL == 0
        assert MbrDeltaSign.POS == 1
        assert MbrDeltaSign.NEG == 255


class TestMbrDelta:
    """Tests for MbrDelta dataclass."""

    def test_zero_delta_null_sign(self) -> None:
        """Test zero delta with NULL sign."""
        delta = MbrDelta(sign=MbrDeltaSign.NULL, amount=0)
        assert delta.is_zero is True
        assert delta.is_positive is False
        assert delta.is_negative is False
        assert delta.signed_amount == 0

    def test_zero_delta_with_amount(self) -> None:
        """Test NULL sign with non-zero amount is treated as zero."""
        delta = MbrDelta(sign=MbrDeltaSign.NULL, amount=100)
        assert delta.is_zero is True
        assert delta.is_positive is False
        assert delta.is_negative is False
        assert delta.signed_amount == 0

    def test_positive_delta(self) -> None:
        """Test positive delta."""
        delta = MbrDelta(sign=MbrDeltaSign.POS, amount=5000)
        assert delta.is_positive is True
        assert delta.is_negative is False
        assert delta.is_zero is False
        assert delta.signed_amount == 5000

    def test_positive_delta_zero_amount(self) -> None:
        """Test positive sign with zero amount."""
        delta = MbrDelta(sign=MbrDeltaSign.POS, amount=0)
        assert delta.is_positive is False
        assert delta.is_negative is False
        assert delta.is_zero is True
        assert delta.signed_amount == 0

    def test_negative_delta(self) -> None:
        """Test negative delta."""
        delta = MbrDelta(sign=MbrDeltaSign.NEG, amount=3000)
        assert delta.is_negative is True
        assert delta.is_positive is False
        assert delta.is_zero is False
        assert delta.signed_amount == -3000

    def test_negative_delta_zero_amount(self) -> None:
        """Test negative sign with zero amount."""
        delta = MbrDelta(sign=MbrDeltaSign.NEG, amount=0)
        assert delta.is_negative is False
        assert delta.is_positive is False
        assert delta.is_zero is True
        assert delta.signed_amount == 0

    def test_from_tuple_null(self) -> None:
        """Test from_tuple with NULL sign."""
        delta = MbrDelta.from_tuple([enums.MBR_DELTA_NULL, 0])
        assert delta.sign == MbrDeltaSign.NULL
        assert delta.amount == 0
        assert delta.is_zero is True

    def test_from_tuple_positive(self) -> None:
        """Test from_tuple with positive delta."""
        delta = MbrDelta.from_tuple([enums.MBR_DELTA_POS, 1000])
        assert delta.sign == MbrDeltaSign.POS
        assert delta.amount == 1000
        assert delta.is_positive is True

    def test_from_tuple_negative(self) -> None:
        """Test from_tuple with negative delta."""
        delta = MbrDelta.from_tuple([enums.MBR_DELTA_NEG, 2000])
        assert delta.sign == MbrDeltaSign.NEG
        assert delta.amount == 2000
        assert delta.is_negative is True

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(ValueError, match="Expected \\(sign, amount\\)"):
            MbrDelta.from_tuple([1])
        with pytest.raises(ValueError, match="Expected \\(sign, amount\\)"):
            MbrDelta.from_tuple([1, 2, 3])

    def test_from_tuple_invalid_sign(self) -> None:
        """Test from_tuple with invalid sign value."""
        with pytest.raises(ValueError, match="Invalid MBR delta sign"):
            MbrDelta.from_tuple([99, 1000])

    def test_from_tuple_negative_amount(self) -> None:
        """Test from_tuple with negative amount."""
        with pytest.raises(ValueError, match="must be non-negative"):
            MbrDelta.from_tuple([enums.MBR_DELTA_POS, -100])


class TestRegistryParameters:
    """Tests for RegistryParameters dataclass."""

    def test_defaults(self) -> None:
        """Test default registry parameters match constants."""
        params = RegistryParameters.defaults()
        assert params.header_size == const.HEADER_SIZE
        assert params.max_metadata_size == const.MAX_METADATA_SIZE
        assert params.short_metadata_size == const.SHORT_METADATA_SIZE
        assert params.page_size == const.PAGE_SIZE
        assert params.first_payload_max_size == const.FIRST_PAYLOAD_MAX_SIZE
        assert params.extra_payload_max_size == const.EXTRA_PAYLOAD_MAX_SIZE
        assert params.replace_payload_max_size == const.REPLACE_PAYLOAD_MAX_SIZE
        assert params.flat_mbr == const.FLAT_MBR
        assert params.byte_mbr == const.BYTE_MBR

    def test_from_tuple(self) -> None:
        """Test from_tuple parsing."""
        values = [50, 30000, 4000, 1000, 2000, 1900, 1950, 2500, 400]
        params = RegistryParameters.from_tuple(values)
        assert params.header_size == 50
        assert params.max_metadata_size == 30000
        assert params.short_metadata_size == 4000
        assert params.page_size == 1000
        assert params.first_payload_max_size == 2000
        assert params.extra_payload_max_size == 1900
        assert params.replace_payload_max_size == 1950
        assert params.flat_mbr == 2500
        assert params.byte_mbr == 400

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(ValueError, match="Expected 9-tuple"):
            RegistryParameters.from_tuple([1, 2, 3])

    def test_mbr_for_box_zero_metadata(self) -> None:
        """Test MBR calculation for box with zero metadata."""
        params = RegistryParameters.defaults()
        mbr = params.mbr_for_box(0)
        expected = const.FLAT_MBR + const.BYTE_MBR * (
            const.ASSET_METADATA_BOX_KEY_SIZE + const.HEADER_SIZE + 0
        )
        assert mbr == expected

    def test_mbr_for_box_small_metadata(self) -> None:
        """Test MBR calculation for box with small metadata."""
        params = RegistryParameters.defaults()
        metadata_size = 100
        mbr = params.mbr_for_box(metadata_size)
        expected = const.FLAT_MBR + const.BYTE_MBR * (
            const.ASSET_METADATA_BOX_KEY_SIZE + const.HEADER_SIZE + metadata_size
        )
        assert mbr == expected

    def test_mbr_for_box_max_metadata(self) -> None:
        """Test MBR calculation for box with max metadata."""
        params = RegistryParameters.defaults()
        mbr = params.mbr_for_box(params.max_metadata_size)
        expected = const.FLAT_MBR + const.BYTE_MBR * (
            const.ASSET_METADATA_BOX_KEY_SIZE
            + const.HEADER_SIZE
            + params.max_metadata_size
        )
        assert mbr == expected

    def test_mbr_delta_creation(self) -> None:
        """Test MBR delta for box creation (old_metadata_size=None)."""
        params = RegistryParameters.defaults()
        new_size = 200
        delta = params.mbr_delta(old_metadata_size=None, new_metadata_size=new_size)

        expected_mbr = params.mbr_for_box(new_size)
        assert delta.is_positive is True
        assert delta.amount == expected_mbr
        assert delta.signed_amount == expected_mbr

    def test_mbr_delta_increase(self) -> None:
        """Test MBR delta for increasing metadata size."""
        params = RegistryParameters.defaults()
        old_size = 100
        new_size = 300
        delta = params.mbr_delta(old_metadata_size=old_size, new_metadata_size=new_size)

        expected_delta = params.mbr_for_box(new_size) - params.mbr_for_box(old_size)
        assert delta.is_positive is True
        assert delta.amount == expected_delta
        assert delta.signed_amount == expected_delta

    def test_mbr_delta_decrease(self) -> None:
        """Test MBR delta for decreasing metadata size."""
        params = RegistryParameters.defaults()
        old_size = 500
        new_size = 200
        delta = params.mbr_delta(old_metadata_size=old_size, new_metadata_size=new_size)

        expected_delta = params.mbr_for_box(old_size) - params.mbr_for_box(new_size)
        assert delta.is_negative is True
        assert delta.amount == expected_delta
        assert delta.signed_amount == -expected_delta

    def test_mbr_delta_no_change(self) -> None:
        """Test MBR delta when size doesn't change."""
        params = RegistryParameters.defaults()
        size = 150
        delta = params.mbr_delta(old_metadata_size=size, new_metadata_size=size)

        assert delta.is_zero is True
        assert delta.amount == 0
        assert delta.signed_amount == 0

    def test_mbr_delta_delete(self) -> None:
        """Test MBR delta for deletion."""
        params = RegistryParameters.defaults()
        old_size = 250
        delta = params.mbr_delta(
            old_metadata_size=old_size, new_metadata_size=0, delete=True
        )

        expected_refund = params.mbr_for_box(old_size)
        assert delta.is_negative is True
        assert delta.amount == expected_refund
        assert delta.signed_amount == -expected_refund


class TestRegistryParametersAdvanced:
    """Advanced tests for RegistryParameters edge cases."""

    def test_mbr_for_box_negative_size_raises(self) -> None:
        """Test mbr_for_box with negative metadata_size."""
        params = RegistryParameters.defaults()

        with pytest.raises(ValueError, match="metadata_size must be non-negative"):
            params.mbr_for_box(-1)

    def test_mbr_delta_negative_new_size_raises(self) -> None:
        """Test mbr_delta with negative new_metadata_size."""
        params = RegistryParameters.defaults()

        with pytest.raises(ValueError, match="new_metadata_size must be non-negative"):
            params.mbr_delta(old_metadata_size=100, new_metadata_size=-1)

    def test_mbr_delta_delete_without_old_size_raises(self) -> None:
        """Test mbr_delta with delete=True but old_metadata_size=None."""
        params = RegistryParameters.defaults()

        with pytest.raises(
            ValueError, match="old_metadata_size must be provided when delete=True"
        ):
            params.mbr_delta(old_metadata_size=None, new_metadata_size=0, delete=True)

    def test_mbr_delta_delete_with_nonzero_new_size_raises(self) -> None:
        """Test mbr_delta with delete=True but new_metadata_size != 0."""
        params = RegistryParameters.defaults()

        with pytest.raises(
            ValueError, match="new_metadata_size must be 0 when delete=True"
        ):
            params.mbr_delta(old_metadata_size=100, new_metadata_size=50, delete=True)


class TestMetadataExistence:
    """Tests for MetadataExistence dataclass."""

    def test_both_exist(self) -> None:
        """Test when both ASA and metadata exist."""
        existence = MetadataExistence(asa_exists=True, metadata_exists=True)
        assert existence.asa_exists is True
        assert existence.metadata_exists is True

    def test_asa_only_exists(self) -> None:
        """Test when only ASA exists."""
        existence = MetadataExistence(asa_exists=True, metadata_exists=False)
        assert existence.asa_exists is True
        assert existence.metadata_exists is False

    def test_neither_exists(self) -> None:
        """Test when neither exists."""
        existence = MetadataExistence(asa_exists=False, metadata_exists=False)
        assert existence.asa_exists is False
        assert existence.metadata_exists is False

    def test_from_tuple(self) -> None:
        """Test from_tuple parsing."""
        existence = MetadataExistence.from_tuple([True, False])
        assert existence.asa_exists is True
        assert existence.metadata_exists is False

    def test_from_tuple_both_true(self) -> None:
        """Test from_tuple with both True."""
        existence = MetadataExistence.from_tuple([True, True])
        assert existence.asa_exists is True
        assert existence.metadata_exists is True

    def test_from_tuple_both_false(self) -> None:
        """Test from_tuple with both False."""
        existence = MetadataExistence.from_tuple([False, False])
        assert existence.asa_exists is False
        assert existence.metadata_exists is False

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(
            ValueError, match="Expected \\(asa_exists, metadata_exists\\)"
        ):
            MetadataExistence.from_tuple([True])
        with pytest.raises(
            ValueError, match="Expected \\(asa_exists, metadata_exists\\)"
        ):
            MetadataExistence.from_tuple([True, False, True])


class TestPagination:
    """Tests for Pagination dataclass."""

    def test_basic_pagination(self) -> None:
        """Test basic pagination values."""
        pagination = Pagination(metadata_size=5000, page_size=1000, total_pages=5)
        assert pagination.metadata_size == 5000
        assert pagination.page_size == 1000
        assert pagination.total_pages == 5

    def test_from_tuple(self) -> None:
        """Test from_tuple parsing."""
        pagination = Pagination.from_tuple([3000, 1000, 3])
        assert pagination.metadata_size == 3000
        assert pagination.page_size == 1000
        assert pagination.total_pages == 3

    def test_from_tuple_zero_metadata(self) -> None:
        """Test from_tuple with zero metadata."""
        pagination = Pagination.from_tuple([0, 1000, 0])
        assert pagination.metadata_size == 0
        assert pagination.page_size == 1000
        assert pagination.total_pages == 0

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(
            ValueError, match="Expected \\(metadata_size, page_size, total_pages\\)"
        ):
            Pagination.from_tuple([1000, 100])


class TestPaginatedMetadata:
    """Tests for PaginatedMetadata dataclass."""

    def test_has_next_page(self) -> None:
        """Test paginated metadata with next page."""
        metadata = PaginatedMetadata(
            has_next_page=True, last_modified_round=1000, page_content=b"page data"
        )
        assert metadata.has_next_page is True
        assert metadata.last_modified_round == 1000
        assert metadata.page_content == b"page data"

    def test_no_next_page(self) -> None:
        """Test paginated metadata without next page."""
        metadata = PaginatedMetadata(
            has_next_page=False, last_modified_round=2000, page_content=b"last page"
        )
        assert metadata.has_next_page is False
        assert metadata.last_modified_round == 2000
        assert metadata.page_content == b"last page"

    def test_from_tuple(self) -> None:
        """Test from_tuple parsing."""
        metadata = PaginatedMetadata.from_tuple([True, 1500, b"content"])
        assert metadata.has_next_page is True
        assert metadata.last_modified_round == 1500
        assert metadata.page_content == b"content"

    def test_from_tuple_empty_content(self) -> None:
        """Test from_tuple with empty content."""
        metadata = PaginatedMetadata.from_tuple([False, 0, b""])
        assert metadata.has_next_page is False
        assert metadata.last_modified_round == 0
        assert metadata.page_content == b""

    def test_from_tuple_invalid_length(self) -> None:
        """Test from_tuple with wrong number of elements."""
        with pytest.raises(
            ValueError,
            match="Expected \\(has_next_page, last_modified_round, page_content\\)",
        ):
            PaginatedMetadata.from_tuple([True, 1000])


class TestPaginatedMetadataAdvanced:
    """Advanced tests for PaginatedMetadata."""

    def test_from_tuple_invalid_has_next_page_type(self) -> None:
        """Test from_tuple with non-bool has_next_page."""
        with pytest.raises(TypeError, match="has_next_page must be bool"):
            PaginatedMetadata.from_tuple(["not bool", 1000, b"data"])

    def test_from_tuple_invalid_last_modified_round_type(self) -> None:
        """Test from_tuple with non-int last_modified_round."""
        with pytest.raises(TypeError, match="last_modified_round must be int"):
            PaginatedMetadata.from_tuple([True, "not int", b"data"])

    def test_from_tuple_page_content_as_list(self) -> None:
        """Test from_tuple with page_content as list of ints."""
        result = PaginatedMetadata.from_tuple([False, 2000, [1, 2, 3, 4, 5]])
        assert result.page_content == b"\x01\x02\x03\x04\x05"


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_set_bit_true(self) -> None:
        """Test _set_bit setting a bit to True."""
        result = _set_bit(bits=0b00000000, mask=0b00000001, value=True)
        assert result == 0b00000001

    def test_set_bit_false(self) -> None:
        """Test _set_bit clearing a bit to False."""
        result = _set_bit(bits=0b11111111, mask=0b00000001, value=False)
        assert result == 0b11111110

    def test_set_bit_preserves_other_bits(self) -> None:
        """Test _set_bit preserves other bits when setting."""
        result = _set_bit(bits=0b10101010, mask=0b00000100, value=True)
        assert result == 0b10101110

    def test_set_bit_preserves_other_bits_when_clearing(self) -> None:
        """Test _set_bit preserves other bits when clearing."""
        result = _set_bit(bits=0b10101110, mask=0b00000100, value=False)
        assert result == 0b10101010

    def test_coerce_bytes_from_bytes(self) -> None:
        """Test _coerce_bytes with bytes input."""
        result = _coerce_bytes(b"hello", name="test")
        assert result == b"hello"

    def test_coerce_bytes_from_bytearray(self) -> None:
        """Test _coerce_bytes with bytearray input."""
        result = _coerce_bytes(bytearray([1, 2, 3]), name="test")
        assert result == b"\x01\x02\x03"

    def test_coerce_bytes_from_list(self) -> None:
        """Test _coerce_bytes with list of ints."""
        result = _coerce_bytes([0, 255, 128], name="test")
        assert result == b"\x00\xff\x80"

    def test_coerce_bytes_from_tuple(self) -> None:
        """Test _coerce_bytes with tuple of ints."""
        result = _coerce_bytes((10, 20, 30), name="test")
        assert result == b"\x0a\x14\x1e"

    def test_coerce_bytes_invalid_string_raises(self) -> None:
        """Test _coerce_bytes with string raises TypeError."""
        with pytest.raises(TypeError, match="must be bytes or a sequence of ints"):
            _coerce_bytes("not bytes", name="test")

    def test_coerce_bytes_invalid_int_raises(self) -> None:
        """Test _coerce_bytes with int raises TypeError."""
        with pytest.raises(TypeError, match="must be bytes or a sequence of ints"):
            _coerce_bytes(42, name="test")

    def test_coerce_bytes_invalid_list_content_raises(self) -> None:
        """Test _coerce_bytes with list of non-ints raises TypeError."""
        with pytest.raises(TypeError, match="must be bytes or a sequence of ints"):
            _coerce_bytes(["not", "ints"], name="test")

    def test_is_nonzero_32_all_zeros(self) -> None:
        """Test _is_nonzero_32 with all zeros."""
        assert _is_nonzero_32(b"\x00" * 32) is False

    def test_is_nonzero_32_one_nonzero(self) -> None:
        """Test _is_nonzero_32 with one non-zero byte."""
        assert _is_nonzero_32(b"\x00" * 31 + b"\x01") is True

    def test_is_nonzero_32_all_nonzero(self) -> None:
        """Test _is_nonzero_32 with all non-zero bytes."""
        assert _is_nonzero_32(b"\xff" * 32) is True

    def test_is_nonzero_32_wrong_length(self) -> None:
        """Test _is_nonzero_32 with wrong length."""
        assert _is_nonzero_32(b"\x01" * 31) is False
        assert _is_nonzero_32(b"\x01" * 33) is False
