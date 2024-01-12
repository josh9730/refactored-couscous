import asyncio
import logging

import pynautobot
import typer
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("backups")
_format = logging.Formatter(fmt="%(levelname)s | %(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log_file = logging.FileHandler("backups.log", mode="w")
log_file.setFormatter(_format)
logger.addHandler(log_file)
logger.setLevel(logging.INFO)

# Create a new Typer app
app = typer.Typer(help="Run backups for Ciena devices.")


async def ping_test(hostname: str, queue: asyncio.Queue) -> None:
    """Run a ping test for a device to validate reachability before adding to output queue.

    hostname: hostname or IP Address for a device that is pingable
    queue: output queue to use to feed the rest of the program
    """
    logger.info(f"Checking reachability for {hostname}")

    # wait on something to run and allow other tasks to run while waiting
    # essentially this is waiting on our ping test for the hostname to complete

    # try replacing this with a time.sleep() instead - the function now becomes 'blocking' and it can't
    # release control to another task
    await asyncio.sleep(2)

    # these are just to test to show that our async program works as expected
    if hostname == "R1":
        # this tests what will happen to the queue if one of the devices 'fails'
        # we need to make sure the program can handle failures like this and not hang
        logger.error(f"{hostname} is not reachable and cannot be backed up!")
    else:
        if hostname == "R3":
            # show what happens if one device takes a long time
            # expect that device will still be added to queue and worked by the 'consumer' while this waits
            await asyncio.sleep(5)

        await queue.put(hostname)


async def run_commands(queue: asyncio.Queue) -> None:
    """Run commands on a given device that is received from the input queue.

    queue: input queue to use to retrieve reachable devices
    """
    hostname = await queue.get()  # grab the next item in the queue
    logger.info(f"Running commands on {hostname}")

    await asyncio.sleep(2)  # 'run commands' on the device and allow other backups to proceed

    queue.task_done()  # let the queue know this task has been completed


async def main(devices: list[str]) -> None:
    """Main function to execute device backups.

    devices: list of hostnames or IPs to backup
    """
    queue = asyncio.Queue()  # create a new queue

    # this is the queue 'producer', meaning it will add items to the queue
    # note that we're creating N tasks for N devices. In our case, 4 tasks
    # see note in devices for info on list comprehension
    producers = [asyncio.create_task(ping_test(hostname, queue)) for hostname in devices]

    # this is the 'consumer', meaning it will consume from the queue
    consumers = [asyncio.create_task(run_commands(queue)) for _ in producers]

    # at this point nothing has been initiated. To start the queue working, we need to initiate the producers
    # gather() launches each of the producer tasks, and runs until all producers have completed
    await asyncio.gather(*producers)

    # closes queue after consumers are done, otherwise it will wait indefinitely on the queue
    await queue.join()


def get_devices_from_nb(api_key: str, url: str) -> list[str]:
    """pip install pynautobot=1.5.1

    set pynautobot to a version that will work with our Nautobot instance.
    """
    nb_waveserver_models = [
        "waveserver",
        "waveserver-5",
        "waveserver-ai",
    ]
    nb = pynautobot.api(url=url, token=api_key)
    nb.http_session.verify = False
    devices = nb.dcim.devices.filter(model=nb_waveserver_models)
    from pprint import pprint

    pprint([device.name for device in devices])
    # return [device.name for device in devices]

    # devices = [f"R{i}" for i in range(1, 5)]
    # return devices


@app.command()  # this makes the function a command in for the Typer app
def ciena_backups(
    api_key: str = typer.Argument(..., help="Device Username"),
    url: str = typer.Argument(..., help="Device Password"),
):
    """Tool to backup Ciena devices."""

    # print(f"Credentials: {username} | {password}")

    # creates a list of four 'routers'
    # simply a placeholder to iterate over while testing async features
    # test this in your IDE if you're unfamilar with python list comprehension, this is equivalent to a for loop
    devices = get_devices_from_nb(api_key, url)

    # devices = []
    # for i in range(1, 5):
    #     devices.append(f"R{i}")

    logger.info("Starting backups")

    asyncio.run(main(devices))

    print("Check log file!")

    logger.info("Finished backups")


if __name__ == "__main__":
    # requires Typer. install with: pip install typer

    # use `python3 async_test.py --help` to look at Typer
    app()
