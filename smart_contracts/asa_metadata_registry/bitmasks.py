# Bits (0 = LSB, 7 = MSB)

# Metadata Identifiers (set by the ASA Metadata Registry; clients just read)
ID_SHORT = 1 << 0  # Short Metadata (derived from size)

# Metadata Flags (set by ASA Manager Address)
FLG_ARC20 = 1 << 0  # reversible
FLG_ARC62 = 1 << 1  # reversible
FLG_RESERVED_2 = 1 << 2  # reversible (reserved; MUST init False)
FLG_RESERVED_3 = 1 << 3  # reversible (reserved; MUST init False)
FLG_ARC3 = 1 << 4  # one-way, creation-only
FLG_ARC89_NATIVE = 1 << 5  # one-way, creation-only
FLG_RESERVED_6 = 1 << 6  # one-way, set-anytime (reserved; MUST init False)
FLG_IMMUTABLE = 1 << 7  # one-way, set-anytime (MSB)

REVERSIBLE_MASK = FLG_ARC20 | FLG_ARC62 | FLG_RESERVED_2 | FLG_RESERVED_3
IRREV_CREATION_ONLY_MASK = FLG_ARC3 | FLG_ARC89_NATIVE
IRREV_ANYTIME_MASK = FLG_RESERVED_6 | FLG_IMMUTABLE
