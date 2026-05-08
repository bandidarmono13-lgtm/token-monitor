#!/usr/bin/env python3

import time
import sys
import getpass
from datetime import datetime, timezone, timedelta
from web3 import Web3


# ============================================================
# INPUT HELPERS
# ============================================================

def prompt(label, default=None, secret=False):
    if default:
        display = f"{label} [{default}]: "
    else:
        display = f"{label}: "

    if secret:
        val = getpass.getpass(display)
    else:
        val = input(display).strip()

    if not val and default:
        return default
    if not val:
        print("  required!")
        return prompt(label, default, secret)
    return val


def prompt_int(label, default=None, min_val=1, max_val=9999999):
    while True:
        try:
            raw = prompt(label, str(default) if default else None)
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  value must be between {min_val}-{max_val}")
        except ValueError:
            print("  must be a number!")


def prompt_datetime():
    print("\n  Format  : YYYY-MM-DD HH:MM")
    print("  Example : 2026-05-07 23:00")
    print("  (enter your local time)")

    while True:
        raw = prompt("  Mint time (local)").strip()
        try:
            dt_local = datetime.strptime(raw, "%Y-%m-%d %H:%M")
            local_ts = time.mktime(dt_local.timetuple())
            dt_utc = datetime.fromtimestamp(local_ts, tz=timezone.utc)

            gmt7 = dt_utc + timedelta(hours=7)
            print(f"  -> UTC   : {dt_utc.strftime('%Y-%m-%d %H:%M')} UTC")
            print(f"  -> WIB   : {gmt7.strftime('%Y-%m-%d %H:%M')} WIB")
            confirm = input("  Correct? (y/n): ").strip().lower()
            if confirm == 'y':
                return dt_utc
        except ValueError:
            print("  Wrong format! Use: YYYY-MM-DD HH:MM")


def sep(char="-", w=55):
    print(char * w)


# ============================================================
# COLLECT CONFIG
# ============================================================

def collect_config():
    print("\n[ CONFIGURATION ]")
    sep()

    print("\n[1] RPC ENDPOINT")
    print("    e.g. https://mainnet.infura.io/v3/YOUR_KEY")
    rpc_url = prompt("    RPC URL")

    print("\n[2] CONTRACT ADDRESS")
    print("    Find it: OpenSea -> item -> Details -> Contract Address")
    while True:
        raw = prompt("    Contract (0x...)")
        if Web3.is_address(raw):
            contract_address = Web3.to_checksum_address(raw)
            print(f"    OK: {contract_address}")
            break
        print("    Invalid Ethereum address!")

    print("\n[3] MINT FUNCTION NAME")
    print("    Check on Etherscan -> Contract -> Write Contract")
    print("    Usually: mint / publicMint / safeMint / mintPublic")
    mint_function = prompt("    Function name", default="mint")

    print("\n[4] MINT PRICE (ETH)")
    print("    0 if free mint")
    while True:
        try:
            price_raw = prompt("    Price per NFT (ETH)", default="0")
            mint_price_eth = float(price_raw)
            break
        except ValueError:
            print("    Numbers only, e.g: 0 or 0.05")

    print("\n[5] MINT AMOUNT")
    mint_amount = prompt_int("    How many to mint", default=1, min_val=1, max_val=20)

    print("\n[6] MINT OPEN TIME")
    mint_time_utc = prompt_datetime()

    print("\n[7] GAS SETTINGS")
    print("    Higher = faster. Check: https://etherscan.io/gastracker")
    gas_limit    = prompt_int("    Gas limit",            default=200000, min_val=50000,  max_val=1000000)
    max_fee      = prompt_int("    Max fee per gas (gwei)", default=50,   min_val=1,      max_val=5000)
    priority_fee = prompt_int("    Priority fee (gwei)",   default=5,    min_val=1,      max_val=500)

    print("    Masukkan path file .txt yang berisi private key")
print("    Contoh: C:\\Users\\Hype GLK\\pk.txt")
pk_file = input("    Path file: ").strip().strip('"')
with open(pk_file, 'r') as f:
    private_key = f.read().strip()
print(f"    ✅ Private key loaded ({len(private_key)} chars)")

    return {
        "rpc_url":         rpc_url,
        "contract_address": contract_address,
        "mint_function":   mint_function,
        "mint_price_eth":  mint_price_eth,
        "mint_amount":     mint_amount,
        "mint_time_utc":   mint_time_utc,
        "gas_limit":       gas_limit,
        "max_fee_gwei":    max_fee,
        "priority_fee_gwei": priority_fee,
        "private_key":     private_key,
    }


# ============================================================
# WEB3
# ============================================================

def build_abi(fn_name):
    return [
        {
            "inputs": [
                {"internalType": "uint256", "name": "quantity", "type": "uint256"}
            ],
            "name": fn_name,
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "maxSupply",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]


def connect(cfg):
    print("\nConnecting...")
    w3 = Web3(Web3.HTTPProvider(cfg["rpc_url"]))

    if not w3.is_connected():
        print(f"Failed to connect: {cfg['rpc_url']}")
        sys.exit(1)

    print(f"Connected | block: {w3.eth.block_number}")

    try:
        account = w3.eth.account.from_key(cfg["private_key"])
    except Exception as e:
        print(f"Invalid private key: {e}")
        sys.exit(1)

    balance_eth = w3.from_wei(w3.eth.get_balance(account.address), "ether")
    print(f"Wallet  : {account.address}")
    print(f"Balance : {balance_eth:.5f} ETH")

    gas_cost   = float(w3.from_wei(cfg["gas_limit"] * w3.to_wei(cfg["max_fee_gwei"], "gwei"), "ether"))
    mint_cost  = cfg["mint_price_eth"] * cfg["mint_amount"]
    total_cost = gas_cost + mint_cost

    print(f"Est. cost: mint {mint_cost:.5f} ETH + gas {gas_cost:.5f} ETH = {total_cost:.5f} ETH")

    if float(balance_eth) < total_cost:
        print(f"WARNING: balance may not be enough (~{total_cost:.5f} ETH needed)")

    return w3, account


def countdown(mint_time_utc):
    print(f"\nWaiting for: {mint_time_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print("(Ctrl+C to cancel)\n")

    try:
        while True:
            now  = datetime.now(timezone.utc)
            diff = (mint_time_utc - now).total_seconds()

            if diff <= 0:
                print("\nGO! Executing...")
                break
            elif diff <= 5:
                print(f"\rT-{diff:.2f}s  READY TO FIRE!      ", end="", flush=True)
                time.sleep(0.05)
            elif diff <= 60:
                print(f"\rT-{diff:.1f}s remaining...          ", end="", flush=True)
                time.sleep(0.5)
            else:
                h = int(diff // 3600)
                m = int((diff % 3600) // 60)
                s = int(diff % 60)
                print(f"\r{h:02d}:{m:02d}:{s:02d} remaining...       ", end="", flush=True)
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(0)


def do_mint(w3, account, cfg):

    SEADROP_ADDRESS  = Web3.to_checksum_address("0x00005EA00Ac477B1030CE78506496e8C2dE24bf5")
    NFT_CONTRACT     = Web3.to_checksum_address(cfg["contract_address"])
    FEE_RECIPIENT    = Web3.to_checksum_address("0x0000a26b00c1F0DF003000390027140000fAa719")
    ZERO_ADDRESS     = "0x0000000000000000000000000000000000000000"

    SEADROP_ABI = [
        {
            "inputs": [
                {"internalType": "address", "name": "nftContract",      "type": "address"},
                {"internalType": "address", "name": "feeRecipient",     "type": "address"},
                {"internalType": "address", "name": "minterIfNotPayer", "type": "address"},
                {"internalType": "uint256", "name": "quantity",         "type": "uint256"}
            ],
            "name": "mintPublic",
            "outputs": [],
            "stateMutability": "payable",
            "type": "function"
        }
    ]

    seadrop   = w3.eth.contract(address=SEADROP_ADDRESS, abi=SEADROP_ABI)
    nonce     = w3.eth.get_transaction_count(account.address)
    value_wei = w3.to_wei(cfg["mint_price_eth"] * cfg["mint_amount"], "ether")

    tx = seadrop.functions.mintPublic(
        NFT_CONTRACT,           # contract NFT
        FEE_RECIPIENT,          # fee recipient OpenSea (WAJIB ini, jangan diganti)
        ZERO_ADDRESS,           # minterIfNotPayer = 0x0 artinya payer = minter
        cfg["mint_amount"]
    ).build_transaction({
        "from":                 account.address,
        "value":                value_wei,
        "gas":                  cfg["gas_limit"],
        "maxFeePerGas":         w3.to_wei(cfg["max_fee_gwei"], "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(cfg["priority_fee_gwei"], "gwei"),
        "nonce":                nonce,
        "chainId":              1,
    })

    signed  = w3.eth.account.sign_transaction(tx, cfg["private_key"])
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    print(f"\nTX SENT: {tx_hash.hex()}")
    print(f"Track  : https://etherscan.io/tx/{tx_hash.hex()}")
    print("Waiting for confirmation...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    if receipt["status"] == 1:
        print(f"\nSUCCESS! Gas used: {receipt['gasUsed']:,}")
        print(f"View   : https://opensea.io/{account.address}")
        return True
    else:
        print("\nTX FAILED! Check Etherscan.")
        return False


# ============================================================
# MAIN
# ============================================================

def main():
    sep("=")
    print("  token-monitor v1.0")
    sep("=")

    cfg = collect_config()

    # Summary
    print()
    sep("=")
    gmt7 = cfg["mint_time_utc"] + timedelta(hours=7)
    print(f"  Contract  : {cfg['contract_address']}")
    print(f"  Function  : {cfg['mint_function']}({cfg['mint_amount']})")
    print(f"  Price     : {cfg['mint_price_eth']} ETH each")
    print(f"  Time (WIB): {gmt7.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Gas       : {cfg['max_fee_gwei']} gwei | tip: {cfg['priority_fee_gwei']} gwei")
    sep("=")

    go = input("\nStart? (y/n): ").strip().lower()
    if go != 'y':
        print("Cancelled.")
        sys.exit(0)

    w3, account = connect(cfg)

    countdown(cfg["mint_time_utc"])

    for attempt in range(1, 4):
        print(f"\nAttempt {attempt}/3...")
        ok = do_mint(w3, account, cfg)
        if ok:
            break
        if attempt < 3:
            print("Retrying in 3s...")
            time.sleep(3)

    print("\nDone.")


if __name__ == "__main__":
    main()
