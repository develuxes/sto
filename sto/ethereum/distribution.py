"""Distribute tokenised shares on Ethereum."""
from decimal import Decimal
from logging import Logger

import colorama
from sto.distribution import DistributionEntry
from sto.ethereum.txservice import EthereumStoredTXService

from sto.ethereum.utils import get_abi, check_good_private_key, create_web3
from sto.ethereum.exceptions import BadContractException
from sto.models.broadcastaccount import _PreparedTransaction

from sto.models.implementation import BroadcastAccount, PreparedTransaction
from sqlalchemy.orm import Session
from typing import Union, Optional, List, Tuple
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput


class NotEnoughTokens(Exception):
    pass



def distribute_tokens(logger: Logger,
                          dbsession: Session,
                          network: str,
                          ethereum_node_url: Union[str, Web3],
                          ethereum_abi_file: Optional[str],
                          ethereum_private_key: Optional[str],
                          ethereum_gas_limit: Optional[int],
                          ethereum_gas_price: Optional[int],
                          token_address: str,
                          dists: List[DistributionEntry]) -> Tuple[List[_PreparedTransaction], int, int]:
    """Issue out a new Ethereum token."""

    txs = []

    check_good_private_key(ethereum_private_key)

    abi = get_abi(ethereum_abi_file)

    web3 = create_web3(ethereum_node_url)

    service = EthereumStoredTXService(network, dbsession, web3, ethereum_private_key, ethereum_gas_price, ethereum_gas_limit, BroadcastAccount, PreparedTransaction)

    logger.info("Starting creating transactions from nonce %s", service.get_next_nonce())

    total = sum([dist.amount * 10**18 for dist in dists])

    available = service.get_raw_token_balance(token_address, abi)
    if total > available:
        raise NotEnoughTokens("Not enough tokens for distribution. Account {} has {} raw token balance, needed {}".format(service.get_or_create_broadcast_account().address, available, total))

    new_distributes = old_distributes = 0

    for d in dists:
        if not service.is_distributed(d.external_id):
            # Going to tx queue
            note = "Distributing tokens, raw amount: {}".format(d.amount)
            service.distribute_tokens(d.external_id, d.address, d.amount, token_address, abi, note)
            new_distributes += 1
        else:
            # CSV reimports
            old_distributes += 1

    logger.info("Prepared transactions for broadcasting for network %s", network)
    return txs, new_distributes, old_distributes
