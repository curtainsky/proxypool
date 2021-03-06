import time
import asyncio
from random import random
import traceback

from proxypool.config import (UPPER_LIMIT, LOWER_LIMIT, CHECK_CYCLE_TIME,
                              CHECK_INTERVAL_TIME, VALIDATE_CYCLE_TIME, UPPER_LIMIT_RATIO)
from proxypool.ext import conn
from proxypool.proxy_crawler import ProxyCrawler
from proxypool.proxy_validator import ProxyValidator
from proxypool.utils import logger


class ProxyPool(object):


    @staticmethod
    async def crawler_start(crawler, validator, proxies, flag):
        """ Start proxy crawler and validator.

        Args:
            crawler: ProxyCrawler object.
            validator: ProxyValidator object.
            proxies: asyncio.Queue object, crawler put proxy and validator get proxy.
            flag: asyncio.Event object, stop flag for 'crawler_stop' function.
        """

        logger.debug('proxy crawler started')
        logger.debug('validator started')
        valid = asyncio.ensure_future(validator.start(proxies))
        await crawler.start()
        await proxies.join()
        valid.cancel() # cancel task when Queue was empty, or it would be blocked at Queue.get method

        flag.set()
        logger.debug('proxy crawler finished')

    @staticmethod
    async def crawler_stop(crawler, flag):
        """Check proxies count if enough to stop proxy crawler.

        Args:
            crawler: ProxyCrawler object.
            flag: asyncio.Event object, stop flag.
        """

        while 1:

            if conn.count > int(UPPER_LIMIT * UPPER_LIMIT_RATIO):
                logger.warning('proxies count approached the upper limit')
                crawler.stop()
                break
            if flag.is_set(): # stop check if crawler and validator finished
                break

            logger.debug('checked proxies count in redis')
            await asyncio.sleep(200 * random())

    @staticmethod
    def extend_proxy_pool():
        """Check proxies count if need to extend proxy pool."""

        loop = asyncio.get_event_loop()
        proxies = asyncio.Queue()
        crawler = ProxyCrawler(proxies)
        validator = ProxyValidator()
        while 1:
            if conn.count > LOWER_LIMIT:
                time.sleep(CHECK_CYCLE_TIME)
                continue

            logger.debug('extend proxy pool started')

            flag = asyncio.Event()
            try:
                loop.run_until_complete(asyncio.gather(
                    ProxyPool.crawler_start(crawler, validator, proxies, flag),
                    ProxyPool.crawler_stop(crawler, flag)
                ))
            except Exception:
                logger.error(traceback.format_exc())

            logger.debug('extend proxy pool finished')
            time.sleep(CHECK_INTERVAL_TIME)
            crawler.reset() # create new flag


def proxy_pool_run():
    ProxyPool.extend_proxy_pool()


if __name__ == "__main__":
    proxy_pool_run()
