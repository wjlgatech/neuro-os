from .b1_vanilla_rag import extract as b1_extract
from .b2_graph_rag import extract as b2_extract
from .b3_summary import extract as b3_extract
from .b4_single_shot import extract as b4_extract
from .b5_reviewed import extract as b5_extract
from .ours_full_loop import extract as ours_extract
from .ours_minus_review import extract as ours_minus_review_extract
from .ours_v2_with_bias_check import extract as ours_v2_extract

EXTRACTORS = {
    "B1_vanilla_rag": b1_extract,
    "B2_graph_rag": b2_extract,
    "B3_summary": b3_extract,
    "B4_single_shot_mechanism_card": b4_extract,
    "B5_reviewed_mechanism_card": b5_extract,
    "Ours_full_loop": ours_extract,
}

ABLATION_EXTRACTORS = {
    "Ours_minus_review": ours_minus_review_extract,
    "Ours_v2_with_bias_check": ours_v2_extract,
}
