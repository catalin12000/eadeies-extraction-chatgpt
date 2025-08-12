from core_.features.permit_prompts import PermitPrompts
from core_.base.datatypes import FeatureConfig
from core_.factory.feature_factory import create_feature


class PermitFeatures:
    ADA = create_feature(
        FeatureConfig(
            name="ada",
            column_name="ΑΔΑ",
            prompt=PermitPrompts.ADA,
            value_type=str,
        )
    )
    KAEK = create_feature(
        FeatureConfig(
            name="kaek",
            column_name="ΚΑΕΚ",
            prompt=PermitPrompts.KAEK,
            value_type=str,
            patterns=[r"(\b\d{11}/\d/\d\b)", r"(\b\d{11}\b)"],
        )
    )
    BUILDING_COVER = create_feature(
        FeatureConfig(
            name="building_cover",
            column_name="Εμβ. κάλυψης κτιρίου",
            prompt=PermitPrompts.BUILDING_COVER,
            value_type=str,
        )
    )
    BUILDING_FLOOR = create_feature(
        FeatureConfig(
            name="building_floor",
            column_name="Εμβ. δόμησης κτιρίου",
            prompt=PermitPrompts.BUILDING_FLOOR,
            value_type=str,
        )
    )
    UNCOVERED_PLOT = create_feature(
        FeatureConfig(
            name="uncovered_plot",
            column_name="Εμβ. ακάλυπτου χώρου οικοπέδου",
            prompt=PermitPrompts.UNCOVERED_PLOT,
            value_type=str,
        )
    )
    VOLUME = create_feature(
        FeatureConfig(
            name="volume",
            column_name="Όγκος κτιρίου (άνω εδάφους)",
            prompt=PermitPrompts.VOLUME,
            value_type=str,
        )
    )
    HEIGHT = create_feature(
        FeatureConfig(
            name="height",
            column_name="Μέγιστο ύψος κτιρίου",
            prompt=PermitPrompts.HEIGHT,
            value_type=str,
        )
    )
    FLOORS = create_feature(
        FeatureConfig(
            name="floors",
            column_name="Όροφοι (άνω εδάφους)",
            prompt=PermitPrompts.FLOORS,
            value_type=str,
        )
    )
    PARKING = create_feature(
        FeatureConfig(
            name="parking",
            column_name="Αριθμός θέσεων στάθμευσης",
            prompt=PermitPrompts.PARKING,
            value_type=str,
        )
    )
    OWNER = create_feature(
        FeatureConfig(
            name="owner",
            column_name="ΙΔΙΟΚΤΗΤΕΣ",
            prompt=PermitPrompts.OWNER,
            value_type=str,
        )
    )
    CAPACITY = create_feature(
        FeatureConfig(
            name="capacity",
            column_name="Ιδιότητα",
            prompt=PermitPrompts.CAPACITY,
            value_type=str,
        )
    )
    TITLE = create_feature(
        FeatureConfig(
            name="title",
            column_name="Τύπος δικαιώματος",
            prompt=PermitPrompts.TITLE,
            value_type=str,
        )
    )

    ALL = [
        ADA,
        KAEK,
        BUILDING_COVER,
        BUILDING_FLOOR,
        UNCOVERED_PLOT,
        VOLUME,
        HEIGHT,
        FLOORS,
        PARKING,
        OWNER,
        CAPACITY,
        TITLE,
    ]
