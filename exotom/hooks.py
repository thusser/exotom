import logging
from exotom.transits import calculate_transits_during_next_n_days

logger = logging.getLogger(__name__)


def target_post_save(target, created):
    # update target
    logger.info('Target post save hook: %s created: %s', target, created)
    calculate_transits_during_next_n_days(target)
