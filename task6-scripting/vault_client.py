import os
import time
import logging
import requests
import hvac
from dotenv import load_dotenv

#Setup for Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

#Loading environment variables
load_dotenv(override=True)
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID")
VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID")

if not all([VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID]):
    raise EnvironmentError(
        "Missing required environment variables. "
        "Ensure VAULT_ADDR, VAULT_ROLE_ID, and VAULT_SECRET_ID are set in environment variables"
    )


SECRET_PATH      = "mykv/data/myapp/config"
RENEW_BEFORE     = 30   # renew token if TTL drops below 300s
TIMEOUT          = 30
MAX_RETRIES      = 3
RETRY_DELAY      = 2

def _make_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Makes an HTTP request with retry logic.
    Retries on connection errors and timeouts up to MAX_RETRIES times.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            log.warning(f"Attempt {attempt}/{MAX_RETRIES} failed: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                log.info(f"Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                raise

# Step 1: Authenticate with AppRole 
def approle_login(role_id: str, secret_id: str) -> dict:
    """
    Authenticates to Vault using AppRole (RoleID + SecretID).
    Returns the full auth response including token and lease duration.
    """
    log.info("Authenticating with Vault via AppRole..")
    print(VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID)
    url = f"{VAULT_ADDR}/v1/auth/approle/login"
    payload = {"role_id": role_id, "secret_id": secret_id}

    try:
        response = _make_request("POST", url, json=payload)
        response.raise_for_status()
        
        auth_data = response.json().get("auth", {})
        token = auth_data.get("client_token")
        ttl   = auth_data.get("lease_duration")

        if not token:
            raise RuntimeError("Login succeeded but no token returned.")

        log.info(f"Login successful. Token TTL: {ttl}s")
        return {"token": token, "ttl": ttl, "created_at": time.time()}

    except requests.exceptions.HTTPError as e:
        log.error(f"HTTP error: {e}")
        log.error(f"Response body: {response.text}")
        raise

# Step 2: Check and renew token if needed (Bonus)
def check_and_renew(token_info: dict) -> dict:
    """
    Checks if token TTL is below RENEW_BEFORE threshold.
    Renews the token if needed and returns updated token info.
    """
    elapsed = time.time() - token_info["created_at"]
    remaining_ttl = token_info["ttl"] - elapsed

    log.info(f"Token TTL check: {remaining_ttl:.0f}s remaining")

    if remaining_ttl < RENEW_BEFORE:
        log.info(f"Token TTL below {RENEW_BEFORE}s threshold. Renewing..")
        try:
            client = hvac.Client(url=VAULT_ADDR, token=token_info["token"])
            renew_response = client.auth.token.renew_self(increment='1h')
            
            new_ttl = renew_response['auth']['lease_duration']
            log.info(f"Token renewed successfully. New TTL: {new_ttl}s")
            
            return {"token": token_info["token"], "ttl": new_ttl, "created_at": time.time()}
        except hvac.exceptions.InvalidRequest as e:
            log.error(f"Token renewal failed: {e}")
            raise
    else:
        log.info(f"Token TTL is within threshold of {RENEW_BEFORE}s . No renewal needed.")
        return token_info

# Step 3: Retrieve a secret
def get_secret(token: str, path: str) -> dict:
    """
    Retrieves a secret from Vault at the given KV v2 path.
    Returns the data dict from the secret.
    """
    log.info(f"Retrieving secret from path: {path}")

    url = f"{VAULT_ADDR}/v1/{path}"
    headers = {"X-Vault-Token": token}

    try:
        response = _make_request("GET", url, headers=headers)
        
        if response.status_code == 403:
            raise PermissionError(
                f"Access denied to {path}. Check token policy."
            )
        if response.status_code == 404:
            raise FileNotFoundError(
                f"Secret not found at path: {path}"
            )
        
        response.raise_for_status()

        secret_data = response.json().get("data", {}).get("data", {})
        log.info(f"Secret retrieved successfully. Keys found: {list(secret_data.keys())}")
        return secret_data
    
    except requests.exceptions.HTTPError as e:
        log.error(f"Failed to retrieve secret: {e}")
        log.error(f"Response body: {response.text}")
        raise



def main():
    try:
        # 1. Login with AppRole
        token_info = approle_login(VAULT_ROLE_ID, VAULT_SECRET_ID)

        #time.sleep(30) - Uncomment this to test renewal functionality

        # 2. Check token health and renew if needed
        token_info = check_and_renew(token_info)

        # 3. Retrieve the secret
        secret = get_secret(token_info["token"], SECRET_PATH)

        # 4. Use the secret (print keys only — only in development and not in production)
        log.info("Secret data retrieved:")
        for key, value in secret.items():
            log.info(f"  {key} = {'*' * len(str(value))}  (masked)")
    
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()