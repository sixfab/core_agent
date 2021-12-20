import time

def check_bulk_deployment(configs, config_path):
    logger = configs["logger"]

    while True:
        if "b_token" in configs:
            logger.debug("Bulk deployment started. BToken: %s", configs["b_token"])
            print("Bulk deployment started. BToken: %s", configs["b_token"])
            do_token_exchange()
        else:
            logger.debug("No bulk deployment exist. Continue...")
            print("No bulk deployment exist. Continue...")
            return
        time.sleep(2)

def do_token_exchange():
    pass
