"""
This module contains the IrohaCli class, which is responsible for building and executing
commands for interacting with Iroha blockchain using the Iroha command-line client.
"""

import shlex
import subprocess
from pathlib import Path
from time import monotonic, sleep
from typing import Callable, Optional

import allure  # type: ignore

from ...common.helpers import extract_hash, read_isi_from_json, write_isi_to_json
from ...common.settings import IROHA_CLI_BINARY, ISI_PATH, IROHA_CLI_CONFIG, BASE_DIR
from .configuration import Config


class IrohaCli:
    """
    A class to represent the Iroha client command line interface.
    """

    BASE_PATH = IROHA_CLI_BINARY
    BASE_FLAGS = ["--config=" + IROHA_CLI_CONFIG]

    def __init__(self, config: Config):
        """
        :param config: The configuration object.
        :type config: Config
        """
        self._config = config
        self.command = [self.BASE_PATH] + self.BASE_FLAGS
        self.stdout: Optional[str] = None
        self.stderr: Optional[str] = None
        self.transaction_hash: Optional[str] = None
        self._timeout = 20

    def __enter__(self):
        """
        Called when entering a context managed by the IrohaCli object.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Called when exiting a context managed by the IrohaCli object.

        :param exc_type: The type of exception raised within the context (if any).
        :param exc_val: The instance of the exception raised within the context (if any).
        :param exc_tb: A traceback object encapsulating the call stack at the point
                        where the exception was raised (if any).
        """
        self.reset()

    def wait_for(self, condition: Callable[[], bool], timeout=None):
        """
        Wait for a certain condition to be met, specified by the expected and actual values.

        :param condition: Condition that should be met in given time.
        :type condition: Callable[[], bool]
        :param timeout: Maximum time to wait for the condition to be met, defaults to None.
        :type timeout: int, optional
        """
        timeout = timeout or self._timeout
        start_time = monotonic()
        while not condition():
            if monotonic() - start_time > timeout:
                raise TimeoutError(
                    f"Expected condition to be satisfied after waiting for '{timeout}' seconds."
                )
            sleep(0.25)

    def reset(self):
        """
        Resets the stdout and stderr attributes of the IrohaCli object.
        """
        self.stdout = None
        self.stderr = None
        self.command = [self.BASE_PATH] + self.BASE_FLAGS

    def register(self):
        """
        Appends the 'register' command to the command list.

        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.append("register")
        return self

    def mint(self):
        """
        Appends the 'mint' command to the command list.

        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.append("mint")
        return self

    def list_all(self):
        """
        Appends the 'list all' command to the command list.

        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.append("list")
        self.command.append("all")
        return self

    def list_filter(self, filter_criteria):
        """
        Appends the 'list filter' command to the command list.

        :param filter_criteria: Criteria to filter the list.
        """
        self.command.append("list")
        self.command.append("filter")
        self.command.append(str(filter_criteria))
        return self

    def domain(self, domain: str):
        """
        Executes the 'domain' command for the given domain.

        :param domain: The domain to be queried.
        :type domain: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.insert(2, "domain")
        self.command.append("--id=" + domain)
        self.execute()
        return self

    def account(self, signatory: str, domain: str):
        """
        Executes the 'account' command for the given signatory and domain.

        :param signatory: The signatory of the account.
        :type signatory: str
        :param domain: The domain of the account.
        :type domain: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.insert(2, "account")
        self.command.append("--id=" + signatory + "@" + domain)
        self.execute()
        return self

    def asset(self, asset_definition=None, account=None, value_of_type=None):
        """
        Executes the 'asset' command with the given asset definition, account, and value.

        :param asset_definition: The asset definition to be queried, defaults to None.
        :type asset_definition: AssetDefinition
        :param account: The account to be queried, defaults to None.
        :type account: Account
        :param value_of_type: The value of the asset type, defaults to None.
        :type value_of_type: str, optional
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.insert(2, "asset")
        if asset_definition and account and value_of_type:
            self.command.append(
                "--id="
                + asset_definition.name
                + "#"
                + asset_definition.domain
                + "#"
                + account.signatory
                + "@"
                + account.domain
            )
            self.command.append("--quantity=" + value_of_type)
            self.execute()
        return self

    def transfer(self, asset, source_account, target_account, quantity: str):
        """
        Executes the 'transfer' command for the given asset.

        :param asset: The asset to be transferred.
        :type asset: str
        :param source_account: The account from which the asset is transferred.
        :type source_account: str
        :param target_account: The account to which the asset is transferred.
        :type target_account: str
        :param quantity: The quantity of the asset to be transferred.
        :type quantity: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.append("asset")
        self.command.append("transfer")
        self.command.append("--to=" + repr(target_account))
        self.command.append(
            "--id="
            + asset.name
            + "#"
            + asset.domain
            + "#"
            + source_account.signatory
            + "@"
            + source_account.domain
        )
        self.command.append("--quantity=" + quantity)
        self.execute()
        return self

    def burn(self, account, asset, quantity: str):
        """
        Executes the 'burn' command for the given asset

        :param account: The account from which the asset is burned.
        :type account: Account
        :param asset: The asset to be burned.
        :type asset: str
        :param quantity: The quantity of the asset to be burned.
        :type quantity: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.append("asset")
        self.command.append("burn")
        self.command.append(
            "--id="
            + asset.name
            + "#"
            + asset.domain
            + "#"
            + account.signatory
            + "@"
            + account.domain
        )
        self.command.append("--quantity=" + quantity)
        self.execute()
        return self

    def asset_definition(self, asset: str, domain: str, scale: Optional[int] = None):
        """
        Executes the 'definition' command for the given asset, domain, and numeric scale.

        :param asset: The asset to be defined.
        :type asset: str
        :param domain: The domain of the asset.
        :type domain: str
        :param scale: The numeric scale of the asset.
        :type scale: int
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.insert(2, "definition")
        self.command.insert(2, "asset")
        self.command.append("--id=" + asset + "#" + domain)
        if scale is not None:
            self.command.append("--scale=" + str(scale))
        self.execute()
        return self

    def nft(self, nft: str, domain: str, content: str = "{}"):
        """
        Executes the 'nft' command for the given nft, domain, and content.

        :param nft: Name of the nft
        :type nft: str
        :param domain: The domain of the MFT.
        :type domain: str
        :param content: The content of the NFT (JSON-serialized object of key-values).
        :type content: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.command.insert(2, "nft")
        self.command.append("--id=" + nft + "$" + domain)

        # Padding `content` as stdin
        self.command = ["echo", content, "|"] + self.command

        self.execute()
        return self

    def _read_and_update_json(self, template_filename, changes=None):
        """
        Reads a JSON template, applies multiple updates, and writes the modified data to a JSON file.

        :param template_filename: The name of the JSON template file.
        :type template_filename: str
        :param changes: A dictionary of updates where each key is a path to a JSON key
        :type changes: dict
        :return: The path to the temporary JSON file.
        :rtype: str
        """
        json_template_path = Path("common") / "json_isi_examples" / template_filename
        data = read_isi_from_json(str(json_template_path))

        if changes:
            for key_path, value in changes.items():
                element = data[0]
                for key in key_path[:-1]:
                    element = element[key]
                element[key_path[-1]] = value

        json_temp_file_path = Path(ISI_PATH) / f"isi_{template_filename}"
        write_isi_to_json(data, str(json_temp_file_path))

        return str(json_temp_file_path)

    def _execute_isi(self, temp_file_path):
        """
        Executes the Iroha CLI command using the provided temporary JSON file.

        :param temp_file_path: The path to the temporary JSON file.
        :type temp_file_path: str
        """
        self._execute_pipe(
            ["cat", temp_file_path],
            [self.BASE_PATH] + self.BASE_FLAGS + ["transaction", "stdin"],
        )

    def register_trigger(self, account):
        """
        Creates a JSON file for the register trigger and executes it using the Iroha CLI.

        :param account: The account to be used in the register_trigger.
        :type account: str
        """
        changes = {
            ("Register", "Trigger", "action", "authority"): str(account),
        }
        temp_file_path = self._read_and_update_json("register_trigger.json", changes)
        self._execute_isi(temp_file_path)
        return self

    def unregister_asset(self, asset):
        """
        Creates a JSON file for the unregister asset and executes it using the Iroha CLI.

        :param asset: The object ID to be used in the unregister_asset.
        :type asset: str
        """
        changes = {
            ("Unregister", "Asset", "object"): str(asset),
        }
        temp_file_path = self._read_and_update_json("unregister_asset.json", changes)
        self._execute_isi(temp_file_path)
        return self

    def grant_permission(self, destination, permission):
        """
        Grants a permission to a destination account.

        :param destination: The account to which the permission is granted.
        :type destination: str
        :param permission: The permission to grant.
        :type permission: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        changes = {
            ("Grant", "Permission", "object", "name"): str(permission),
            ("Grant", "Permission", "destination"): str(destination),
        }
        temp_file_path = self._read_and_update_json("grant_permission.json", changes)
        self._execute_isi(temp_file_path)
        return self

    def revoke_permission(self, destination, permission):
        """
        Revokes a permission from a destination account.

        :param destination: The account from which the permission is revoked.
        :type destination: str
        :param permission: The permission to revoke.
        :type permission: str
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        changes = {
            ("Revoke", "Permission", "object", "name"): str(permission),
            ("Revoke", "Permission", "destination"): str(destination),
        }
        temp_file_path = self._read_and_update_json("revoke_permission.json", changes)
        self._execute_isi(temp_file_path)
        return self

    def send_wrong_instruction(self):
        """
        Creates a JSON file for the send_wrong_instruction and executes it using the Iroha CLI.
        """
        temp_file_path = self._read_and_update_json("wrong_instruction.json")
        self._execute_isi(temp_file_path)
        return self

    def should(self, _expected):
        """
        Placeholder method for implementing assertions.

        :param _expected: The expected value.
        :type _expected: Any
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        return self

    def execute(self, command=None):
        """
        Executes the command and captures stdout and stderr.

        :param command: The command to execute, defaults to None.
        :type command: Optional[List[str]]
        :return: The current IrohaCli object.
        :rtype: IrohaCli
        """
        self.config.randomise_torii_url()
        if command is None:
            command = self.command
        else:
            command = [self.BASE_PATH] + self.BASE_FLAGS + shlex.split(command)

        if "|" in command:
            pipe_index = command.index("|")
            self._execute_pipe(command[:pipe_index], command[pipe_index + 1 :])
        else:
            self._execute_single(command)

        self.command = [self.BASE_PATH] + self.BASE_FLAGS
        return self

    def _execute_pipe(self, cmd1, cmd2):
        """
        Executes two commands connected by a pipe.
        """
        with (
            subprocess.Popen(
                cmd1, stdout=subprocess.PIPE, env=self.config.env
            ) as proc1,
            subprocess.Popen(
                cmd2,
                stdin=proc1.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.config.env,
                text=True,
            ) as proc2,
        ):
            self.stdout, self.stderr = proc2.communicate()
            self.transaction_hash = extract_hash(self.stdout)
            self._attach_allure_reports()

    def _execute_single(self, command):
        """
        Executes a single command.
        """
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self.config.env,
        ) as process:
            self.stdout, self.stderr = process.communicate()
            self.transaction_hash = extract_hash(self.stdout)
            self._attach_allure_reports()

    def _attach_allure_reports(self):
        """
        Attaches stdout and stderr to Allure reports.
        """
        allure.attach(
            self.stdout, name="stdout", attachment_type=allure.attachment_type.TEXT
        )
        allure.attach(
            self.stderr, name="stderr", attachment_type=allure.attachment_type.TEXT
        )

    @property
    def config(self) -> Config:
        """
        Getter for the 'config' attribute.

        :return: The configuration object.
        :rtype: Config
        """
        return self._config

    @config.setter
    def config(self, value):
        """
        Setter for the 'config' attribute.

        :param value: The new configuration object.
        :type value: Config
        """
        self._config = value

    def version(self):
        """
        Appends the 'version' command to the command list and executes it.
        """
        self.command.append("version")
        self.execute()
        return self
