from . import flags

# Metadata Identifiers byte (set by the ASA Metadata Registry; clients just read)
MASK_ID_SHORT = 1 << flags.ID_SHORT

# Reversible Flags byte (set by ASA Manager Address)
MASK_REV_ARC20 = 1 << flags.REV_FLG_ARC20
MASK_REV_ARC62 = 1 << flags.REV_FLG_ARC62
MASK_REV_RESERVED_2 = 1 << flags.REV_FLG_RESERVED_2  # TODO: rename MASK_REV_NTT
MASK_REV_RESERVED_3 = 1 << flags.REV_FLG_RESERVED_3
MASK_REV_RESERVED_4 = 1 << flags.REV_FLG_RESERVED_4
MASK_REV_RESERVED_5 = 1 << flags.REV_FLG_RESERVED_5
MASK_REV_RESERVED_6 = 1 << flags.REV_FLG_RESERVED_6
MASK_REV_RESERVED_7 = 1 << flags.REV_FLG_RESERVED_7

# Irreversible Flags byte (set by ASA Manager Address)
MASK_IRR_ARC3 = 1 << flags.IRR_FLG_ARC3
MASK_IRR_ARC89_NATIVE = (
    1 << flags.IRR_FLG_ARC89_NATIVE
)  # TODO: rename to MASK_IRR_ARC89
MASK_IRR_RESERVED_2 = 1 << flags.IRR_FLG_RESERVED_2  # TODO: rename to MASK_IRR_ARC54
MASK_IRR_RESERVED_3 = 1 << flags.IRR_FLG_RESERVED_3
MASK_IRR_RESERVED_4 = 1 << flags.IRR_FLG_RESERVED_4
MASK_IRR_RESERVED_5 = 1 << flags.IRR_FLG_RESERVED_5
MASK_IRR_RESERVED_6 = 1 << flags.IRR_FLG_RESERVED_6
MASK_IRR_IMMUTABLE = 1 << flags.IRR_FLG_IMMUTABLE
