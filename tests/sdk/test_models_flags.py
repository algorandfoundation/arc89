"""
Unit tests for flag models in src.models.

Tests cover:
- ReversibleFlags
- IrreversibleFlags
- MetadataFlags
"""

import pytest

from asa_metadata_registry import (
    IrreversibleFlags,
    MetadataFlags,
    MetadataHeader,
    ReversibleFlags,
    bitmasks,
)


class TestReversibleFlags:
    """Tests for ReversibleFlags dataclass."""

    def test_empty_flags(self) -> None:
        """Test creating empty flags."""
        flags = ReversibleFlags.empty()
        assert flags.arc20 is False
        assert flags.arc62 is False
        assert flags.ntt is False
        assert flags.reserved_3 is False
        assert flags.reserved_4 is False
        assert flags.reserved_5 is False
        assert flags.reserved_6 is False
        assert flags.reserved_7 is False
        assert flags.byte_value == 0

    def test_arc20_flag(self) -> None:
        """Test ARC-20 flag."""
        flags = ReversibleFlags(arc20=True)
        assert flags.arc20 is True
        assert flags.byte_value == bitmasks.MASK_REV_ARC20
        assert flags.byte_value == 0b00000001

    def test_arc62_flag(self) -> None:
        """Test ARC-62 flag."""
        flags = ReversibleFlags(arc62=True)
        assert flags.arc62 is True
        assert flags.byte_value == bitmasks.MASK_REV_ARC62
        assert flags.byte_value == 0b00000010

    def test_ntt_flag(self) -> None:
        """Test NTT flag."""
        flags = ReversibleFlags(ntt=True)
        assert flags.ntt is True
        assert flags.byte_value == bitmasks.MASK_REV_NTT
        assert flags.byte_value == 0b00000100

    def test_multiple_flags(self) -> None:
        """Test multiple flags set simultaneously."""
        flags = ReversibleFlags(arc20=True, arc62=True, ntt=True)
        assert flags.arc20 is True
        assert flags.arc62 is True
        assert flags.ntt is True
        assert flags.byte_value == (
            bitmasks.MASK_REV_ARC20 | bitmasks.MASK_REV_ARC62 | bitmasks.MASK_REV_NTT
        )
        assert flags.byte_value == 0b00000111

    def test_all_flags_set(self) -> None:
        """Test all flags set to True."""
        flags = ReversibleFlags(
            arc20=True,
            arc62=True,
            ntt=True,
            reserved_3=True,
            reserved_4=True,
            reserved_5=True,
            reserved_6=True,
            reserved_7=True,
        )
        assert flags.byte_value == 0b11111111

    def test_from_byte_zero(self) -> None:
        """Test from_byte with 0."""
        flags = ReversibleFlags.from_byte(0)
        assert flags.arc20 is False
        assert flags.arc62 is False
        assert flags.ntt is False
        assert flags.byte_value == 0

    def test_from_byte_arc20(self) -> None:
        """Test from_byte with ARC-20 flag set."""
        flags = ReversibleFlags.from_byte(bitmasks.MASK_REV_ARC20)
        assert flags.arc20 is True
        assert flags.arc62 is False
        assert flags.ntt is False
        assert flags.byte_value == bitmasks.MASK_REV_ARC20

    def test_from_byte_arc62(self) -> None:
        """Test from_byte with ARC-62 flag set."""
        flags = ReversibleFlags.from_byte(bitmasks.MASK_REV_ARC62)
        assert flags.arc62 is True
        assert flags.arc20 is False
        assert flags.ntt is False
        assert flags.byte_value == bitmasks.MASK_REV_ARC62

    def test_from_byte_ntt(self) -> None:
        """Test from_byte with NTT flag set."""
        flags = ReversibleFlags.from_byte(bitmasks.MASK_REV_NTT)
        assert flags.ntt is True
        assert flags.arc20 is False
        assert flags.arc62 is False
        assert flags.byte_value == bitmasks.MASK_REV_NTT

    def test_from_byte_multiple(self) -> None:
        """Test from_byte with multiple flags."""
        value = (
            bitmasks.MASK_REV_ARC20 | bitmasks.MASK_REV_ARC62 | bitmasks.MASK_REV_NTT
        )
        flags = ReversibleFlags.from_byte(value)
        assert flags.arc20 is True
        assert flags.arc62 is True
        assert flags.ntt is True
        assert flags.byte_value == value

    def test_from_byte_all_flags(self) -> None:
        """Test from_byte with all flags set."""
        flags = ReversibleFlags.from_byte(0xFF)
        assert flags.arc20 is True
        assert flags.arc62 is True
        assert flags.ntt is True
        assert flags.reserved_3 is True
        assert flags.reserved_4 is True
        assert flags.reserved_5 is True
        assert flags.reserved_6 is True
        assert flags.reserved_7 is True
        assert flags.byte_value == 0b11111111

    def test_from_byte_invalid_negative(self) -> None:
        """Test from_byte with negative value raises."""
        with pytest.raises(ValueError, match="Byte value must be 0-255"):
            ReversibleFlags.from_byte(-1)

    def test_from_byte_invalid_too_large(self) -> None:
        """Test from_byte with value > 255 raises."""
        with pytest.raises(ValueError, match="Byte value must be 0-255"):
            ReversibleFlags.from_byte(256)

    def test_round_trip_conversion(self) -> None:
        """Test round-trip conversion flags -> byte -> flags."""
        original = ReversibleFlags(arc20=True, reserved_3=True, reserved_7=True)
        byte_val = original.byte_value
        reconstructed = ReversibleFlags.from_byte(byte_val)
        assert reconstructed == original
        assert reconstructed.byte_value == byte_val


class TestIrreversibleFlags:
    """Tests for IrreversibleFlags dataclass."""

    def test_empty_flags(self) -> None:
        """Test creating empty flags."""
        flags = IrreversibleFlags.empty()
        assert flags.arc3 is False
        assert flags.arc89_native is False
        assert flags.burnable is False
        assert flags.reserved_3 is False
        assert flags.reserved_4 is False
        assert flags.reserved_5 is False
        assert flags.reserved_6 is False
        assert flags.immutable is False
        assert flags.byte_value == 0

    def test_arc3_flag(self) -> None:
        """Test ARC-3 flag."""
        flags = IrreversibleFlags(arc3=True)
        assert flags.arc3 is True
        assert flags.byte_value == bitmasks.MASK_IRR_ARC3
        assert flags.byte_value == 0b00000001

    def test_arc89_native_flag(self) -> None:
        """Test ARC-89 native flag."""
        flags = IrreversibleFlags(arc89_native=True)
        assert flags.arc89_native is True
        assert flags.byte_value == bitmasks.MASK_IRR_ARC89
        assert flags.byte_value == 0b00000010

    def test_arc54_burnable_flag(self) -> None:
        """Test ARC-54 burnable flag."""
        flags = IrreversibleFlags(burnable=True)
        assert flags.burnable is True
        assert flags.byte_value == bitmasks.MASK_IRR_ARC54
        assert flags.byte_value == 0b00000100

    def test_immutable_flag(self) -> None:
        """Test immutable flag."""
        flags = IrreversibleFlags(immutable=True)
        assert flags.immutable is True
        assert flags.byte_value == bitmasks.MASK_IRR_IMMUTABLE
        assert flags.byte_value == 0b10000000

    def test_multiple_flags(self) -> None:
        """Test multiple flags set simultaneously."""
        flags = IrreversibleFlags(
            arc3=True, arc89_native=True, burnable=True, immutable=True
        )
        assert flags.arc3 is True
        assert flags.arc89_native is True
        assert flags.burnable is True
        assert flags.immutable is True
        assert flags.byte_value == (
            bitmasks.MASK_IRR_ARC3
            | bitmasks.MASK_IRR_ARC89
            | bitmasks.MASK_IRR_ARC54
            | bitmasks.MASK_IRR_IMMUTABLE
        )
        assert flags.byte_value == 0b10000111

    def test_all_flags_set(self) -> None:
        """Test all flags set to True."""
        flags = IrreversibleFlags(
            arc3=True,
            arc89_native=True,
            burnable=True,
            reserved_3=True,
            reserved_4=True,
            reserved_5=True,
            reserved_6=True,
            immutable=True,
        )
        assert flags.byte_value == 0b11111111

    def test_from_byte_zero(self) -> None:
        """Test from_byte with 0."""
        flags = IrreversibleFlags.from_byte(0)
        assert flags.arc3 is False
        assert flags.immutable is False
        assert flags.byte_value == 0

    def test_from_byte_arc3(self) -> None:
        """Test from_byte with ARC-3 flag set."""
        flags = IrreversibleFlags.from_byte(bitmasks.MASK_IRR_ARC3)
        assert flags.arc3 is True
        assert flags.arc89_native is False
        assert flags.burnable is False
        assert flags.immutable is False
        assert flags.byte_value == bitmasks.MASK_IRR_ARC3

    def test_from_byte_arc89_native(self) -> None:
        """Test from_byte with ARC-89 native flag set."""
        flags = IrreversibleFlags.from_byte(bitmasks.MASK_IRR_ARC89)
        assert flags.arc89_native is True
        assert flags.arc3 is False
        assert flags.burnable is False
        assert flags.immutable is False
        assert flags.byte_value == bitmasks.MASK_IRR_ARC89

    def test_from_byte_arc54_burnable(self) -> None:
        """Test from_byte with ARC-54 burnable flag set."""
        flags = IrreversibleFlags.from_byte(bitmasks.MASK_IRR_ARC54)
        assert flags.burnable is True
        assert flags.arc3 is False
        assert flags.arc89_native is False
        assert flags.immutable is False
        assert flags.byte_value == bitmasks.MASK_IRR_ARC54

    def test_from_byte_immutable(self) -> None:
        """Test from_byte with immutable flag set."""
        flags = IrreversibleFlags.from_byte(bitmasks.MASK_IRR_IMMUTABLE)
        assert flags.immutable is True
        assert flags.arc3 is False
        assert flags.arc89_native is False
        assert flags.burnable is False
        assert flags.byte_value == bitmasks.MASK_IRR_IMMUTABLE

    def test_from_byte_multiple(self) -> None:
        """Test from_byte with multiple flags."""
        value = bitmasks.MASK_IRR_ARC3 | bitmasks.MASK_IRR_IMMUTABLE
        flags = IrreversibleFlags.from_byte(value)
        assert flags.arc3 is True
        assert flags.immutable is True
        assert flags.arc89_native is False
        assert flags.burnable is False
        assert flags.byte_value == value

    def test_from_byte_all_flags(self) -> None:
        """Test from_byte with all flags set."""
        flags = IrreversibleFlags.from_byte(0xFF)
        assert flags.arc3 is True
        assert flags.arc89_native is True
        assert flags.burnable is True
        assert flags.reserved_3 is True
        assert flags.reserved_4 is True
        assert flags.reserved_5 is True
        assert flags.reserved_6 is True
        assert flags.immutable is True
        assert flags.byte_value == 0b11111111

    def test_from_byte_invalid_negative(self) -> None:
        """Test from_byte with negative value raises."""
        with pytest.raises(ValueError, match="Byte value must be 0-255"):
            IrreversibleFlags.from_byte(-1)

    def test_from_byte_invalid_too_large(self) -> None:
        """Test from_byte with value > 255 raises."""
        with pytest.raises(ValueError, match="Byte value must be 0-255"):
            IrreversibleFlags.from_byte(256)

    def test_round_trip_conversion(self) -> None:
        """Test round-trip conversion flags -> byte -> flags."""
        original = IrreversibleFlags(arc3=True, burnable=True, immutable=True)
        byte_val = original.byte_value
        reconstructed = IrreversibleFlags.from_byte(byte_val)
        assert reconstructed == original
        assert reconstructed.byte_value == byte_val


class TestMetadataFlags:
    """Tests for MetadataFlags combined flags."""

    def test_empty_flags(self) -> None:
        """Test creating empty combined flags."""
        flags = MetadataFlags.empty()
        assert flags.reversible.byte_value == 0
        assert flags.irreversible.byte_value == 0
        assert flags.reversible_byte == 0
        assert flags.irreversible_byte == 0

    def test_from_bytes_both_zero(self) -> None:
        """Test from_bytes with both bytes zero."""
        flags = MetadataFlags.from_bytes(0, 0)
        assert flags.reversible_byte == 0
        assert flags.irreversible_byte == 0

    def test_from_bytes_reversible_only(self) -> None:
        """Test from_bytes with only reversible flags set."""
        rev_byte = bitmasks.MASK_REV_ARC20
        flags = MetadataFlags.from_bytes(rev_byte, 0)
        assert flags.reversible_byte == rev_byte
        assert flags.irreversible_byte == 0
        assert flags.reversible.arc20 is True
        assert flags.irreversible.arc3 is False

    def test_from_bytes_irreversible_only(self) -> None:
        """Test from_bytes with only irreversible flags set."""
        irr_byte = bitmasks.MASK_IRR_ARC3
        flags = MetadataFlags.from_bytes(0, irr_byte)
        assert flags.reversible_byte == 0
        assert flags.irreversible_byte == irr_byte
        assert flags.reversible.arc20 is False
        assert flags.irreversible.arc3 is True

    def test_from_bytes_both_set(self) -> None:
        """Test from_bytes with both reversible and irreversible flags."""
        rev_byte = bitmasks.MASK_REV_ARC20 | bitmasks.MASK_REV_ARC62
        irr_byte = bitmasks.MASK_IRR_ARC3 | bitmasks.MASK_IRR_IMMUTABLE
        flags = MetadataFlags.from_bytes(rev_byte, irr_byte)

        assert flags.reversible_byte == rev_byte
        assert flags.irreversible_byte == irr_byte
        assert flags.reversible.arc20 is True
        assert flags.reversible.arc62 is True
        assert flags.irreversible.arc3 is True
        assert flags.irreversible.immutable is True

    def test_from_bytes_all_flags(self) -> None:
        """Test from_bytes with all flags set."""
        flags = MetadataFlags.from_bytes(0xFF, 0xFF)
        assert flags.reversible_byte == 0xFF
        assert flags.irreversible_byte == 0xFF

    def test_construct_with_flag_objects(self) -> None:
        """Test constructing MetadataFlags with flag objects."""
        rev = ReversibleFlags(arc20=True, arc62=True)
        irr = IrreversibleFlags(arc3=True, immutable=True)
        flags = MetadataFlags(reversible=rev, irreversible=irr)

        assert flags.reversible == rev
        assert flags.irreversible == irr
        assert flags.reversible_byte == rev.byte_value
        assert flags.irreversible_byte == irr.byte_value

    def test_round_trip_conversion(self) -> None:
        """Test round-trip conversion."""
        original = MetadataFlags.from_bytes(0xAB, 0xCD)
        rev_byte = original.reversible_byte
        irr_byte = original.irreversible_byte
        reconstructed = MetadataFlags.from_bytes(rev_byte, irr_byte)

        assert reconstructed.reversible_byte == rev_byte
        assert reconstructed.irreversible_byte == irr_byte
        assert reconstructed.reversible == original.reversible
        assert reconstructed.irreversible == original.irreversible


class TestFlagsUseCases:
    """Test real-world use cases."""

    def test_arc3_nft(self):
        """Test flags for a standard ARC-3 NFT."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc3=True),
        )
        assert flags.irreversible_byte == 1
        assert flags.reversible_byte == 0

    def test_arc54_burnable(self):
        """Test flags for a standard ARC-54 burnable ASA."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(burnable=True),
        )
        assert flags.irreversible_byte == 4
        assert flags.reversible_byte == 0

    def test_immutable_arc3_nft(self):
        """Test flags for an immutable ARC-3 NFT."""
        flags = MetadataFlags(
            reversible=ReversibleFlags.empty(),
            irreversible=IrreversibleFlags(arc3=True, immutable=True),
        )
        assert flags.irreversible_byte == 129

    def test_arc20_smart_asa(self):
        """Test flags for an ARC-20 Smart ASA."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc20=True),
            irreversible=IrreversibleFlags.empty(),
        )
        assert flags.reversible_byte == 1

    def test_arc62_circulating_supply(self):
        """Test flags for ARC-62 circulating supply tracking."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(arc62=True),
            irreversible=IrreversibleFlags.empty(),
        )
        assert flags.reversible_byte == 2

    def test_ntt_native_token_transfer(self):
        """Test flags for NTT (Native Token Transfer) ASA."""
        flags = MetadataFlags(
            reversible=ReversibleFlags(ntt=True),
            irreversible=IrreversibleFlags.empty(),
        )
        assert flags.reversible_byte == 4

    def test_parse_existing_metadata(self):
        """Test parsing existing metadata flags from chain."""
        # Simulate reading from chain
        reversible_byte = 3  # arc20 + arc62
        irreversible_byte = 129  # arc3 + immutable

        flags = MetadataFlags.from_bytes(
            reversible=reversible_byte, irreversible=irreversible_byte
        )

        assert flags.irreversible.arc3 is True
        assert flags.irreversible.immutable is True
        assert flags.reversible.arc20 is True
        assert flags.reversible.arc62 is True


class TestMetadataHeaderIntegration:
    """Test integration with MetadataHeader."""

    def test_metadata_header_get_flags(self):
        """Test that MetadataHeader.get_flags() returns correct MetadataFlags."""

        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.from_bytes(3, 129),  # arc3 + arc20 + arc62 + immutable
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )

        flags = header.flags

        assert flags.reversible.arc20 is True
        assert flags.reversible.arc62 is True
        assert flags.irreversible.arc3 is True
        assert flags.irreversible.immutable is True

    def test_metadata_header_convenience_properties(self):
        """Test that existing header properties still work."""

        header = MetadataHeader(
            identifiers=0,
            flags=MetadataFlags.from_bytes(3, 129),  # arc3 + arc20 + arc62 + immutable
            metadata_hash=b"\x00" * 32,
            last_modified_round=1000,
            deprecated_by=0,
        )

        # Test existing convenience properties
        assert header.is_arc3_compliant is True
        assert header.is_immutable is True
        assert header.is_arc20_smart_asa is True
        assert header.is_arc62_circulating_supply is True
