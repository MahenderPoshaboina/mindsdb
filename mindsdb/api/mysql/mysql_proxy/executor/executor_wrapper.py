from flask import Flask, request

from mindsdb.utilities.config import Config
from mindsdb.utilities.log import (
    initialize_log,
    get_log
)
from mindsdb.utilities.context import context as ctx
from mindsdb.api.mysql.mysql_proxy.executor.executor import Executor
from mindsdb.api.mysql.mysql_proxy.controllers.session_controller import SessionController
# from mindsdb.api.mysql.mysql_proxy.controllers.session_controller import ServiceSessionController


Config()
initialize_log(logger_name="main")
logger = get_log("main")


class SqlServerStub:
    def __init__(self, **kwargs):
        for arg in kwargs:
            setattr(self, arg, kwargs[arg])


class ExecutorService:

    def __init__(self):
        self.app = Flask(self.__class__.__name__)
        self.executors_cache = {}
        self.sessions_cache = {}

        default_router = self.app.route("/", methods = ["GET",])
        self.index = default_router(self.index)

        delete_executer_router = self.app.route("/executor", methods = ["DELETE", "DEL", ])
        self.del_executor = delete_executer_router(self.del_executor)


        delete_session_router = self.app.route("/session", methods = ["DELETE", "DEL"])
        self.del_session = delete_session_router(self.del_session)

        stmt_prepare_router = self.app.route("/stmt_prepare", methods = ["POST", ])
        self.stmt_prepare = stmt_prepare_router(self.stmt_prepare)

        stmt_execute_router = self.app.route("/stmt_execute", methods = ["POST", ])
        self.stmt_execute = stmt_execute_router(self.stmt_execute)

        query_execute_router = self.app.route("/query_execute", methods = ["POST", ])
        self.query_execute = query_execute_router(self.query_execute)

        execute_external_router = self.app.route("/execute_external", methods = ["POST", ])
        self.execute_external = execute_external_router(self.execute_external)

        parse_router = self.app.route("/parse", methods = ["POST", ])
        self.parse = parse_router(self.parse)

        do_execute_router = self.app.route("/do_execute", methods = ["POST", ])
        self.do_execute = do_execute_router(self.do_execute)
        logger.info("%s: base params and route have been initialized", self.__class__.__name__)

    def _get_executor(self, params):
        # We have to send context between client and server
        # here we load the context json received from the client(mindsdb)
        # to the local context instance in this Flask thread
        ctx.load(params["context"])
        exec_id = params["id"]
        if exec_id in self.executors_cache:
            logger.info("%s: executor %s found in cache", self.__class__.__name__, exec_id)
            return self.executors_cache[exec_id]
        session_id = params["session_id"]
        if session_id in self.sessions_cache:
            logger.info("%s: session %s found in cache", self.__class__.__name__, session_id)
            session = self.sessions_cache[session_id]
        else:
            logger.info("%s: creating new session. id - %s, params - %s",
                    self.__class__.__name__,
                    session_id,
                    params["session"],
                )
            session = SessionController()
            self.sessions_cache[session_id] = session
        session.database = params["session"]["database"]
        session.username = params["session"]["username"]
        session.auth = params["session"]["auth"]
        session.prepared_stmts = params["session"]["prepared_stmts"]
        session.packet_sequence_number = params["session"]["packet_sequence_number"]
        sqlserver = SqlServerStub(connection_id=params["connection_id"])

        logger.info("%s: session info - id=%s, params=%s",
                self.__class__.__name__,
                session_id,
                session.to_json(),
            )
        logger.info("%s: creating new executor. id - %s, session_id - %s",
                self.__class__.__name__,
                exec_id,
                session_id,
            )
        executor = Executor(session, sqlserver)
        self.executors_cache[exec_id] = executor
        return executor

    def run(self, **kwargs):
        """ Launch internal Flask application."""
        self.app.run(**kwargs)

    def index(self):
        """ Default GET endpoint - '/'."""
        return "An Executor Wrapper", 200

    def del_executor(self):
        # to delete executors
        exec_id = request.json.get("id")
        logger.info("%s: removing executor instance. id - %s", self.__class__.__name__, exec_id)
        if exec_id is not None and exec_id in self.executors_cache:
            del self.executors_cache[exec_id]
        return "", 200

    def del_session(self):
        # to delete sessions
        session_id = request.json.get("id")
        logger.info("%s: removing session instance. id - %s", self.__class__.__name__, session_id)
        if session_id is not None and session_id in self.sessions_cache:
            del self.sessions_cache[session_id]
        return "", 200

    def stmt_prepare(self):
        params = request.json
        logger.info("%s.stmt_prepare: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        sql = params.get("sql")
        executor.stmt_prepare(sql)
        resp = executor.to_json()
        return resp, 200

    def stmt_execute(self):
        params = request.json
        logger.info("%s.stmt_execute: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        param_values = params.get("param_values")
        executor.stmt_execute(param_values)
        resp = executor.to_json()
        return resp, 200

    def query_execute(self):
        params = request.json
        logger.info("%s.query_execute: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        sql = params.get("sql")
        executor.query_execute(sql)
        logger.info("%s.query_execute: executor.data(type of %s) - %s", self.__class__.__name__, type(executor.data), executor.data)
        logger.info("%s.query_execute: executor.columns(type of %s) - %s", self.__class__.__name__, type(executor.columns), executor.columns)
        logger.info("%s.query_execute: executor.params(type of %s) - %s", self.__class__.__name__, type(executor.params), executor.params)

        resp = executor.to_json()
        return resp, 200

    def execute_external(self):
        params = request.json
        logger.info("%s.execute_external: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        sql = params.get("sql")
        executor.execute_external(sql)
        resp = executor.to_json()
        return resp, 200

    def parse(self):
        params = request.json
        logger.info("%s.parse: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        sql = params.get("sql")
        executor.parse(sql)
        resp = executor.to_json()
        return resp, 200

    def do_execute(self):
        params = request.json
        logger.info("%s.do_execute: json received - %s", self.__class__.__name__, params)
        executor = self._get_executor(params)
        executor.do_execute()
        resp = executor.to_json()
        return resp, 200
