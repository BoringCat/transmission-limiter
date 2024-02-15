import logging

class Blocker():
    @property
    def iplist(self): yield from self.__iplist
    @staticmethod
    def doRuleFilter(rule:dict[str, str | int | float | bool], data:str | int | float | bool):
        result = True
        if isinstance(data, str):
            for method, r in rule.items():
                if method == 'prefix':
                    result &= data.startswith(r)
                elif method == 'suffix':
                    result &= data.endswith(r)
                elif method == 'contains':
                    result &= r in data
                elif method == 'equal':
                    result &= data == r
        elif isinstance(data, bool):
            for method, r in rule.items():
                if method == 'equal':
                    result &= data == r
        elif isinstance(data, (int, float)):
            for method, r in rule.items():
                if method == 'equal':
                    result &= data == r
                elif method == 'gt':
                    result &= data > r
                elif method == 'gte':
                    result &= data >= r
                elif method == 'lt':
                    result &= data < r
                elif method == 'lte':
                    result &= data <= r
        return result

    def __init__(self, conf:dict[str, list[str|dict[str, str]]]):
        conf = {} if not isinstance(conf, dict) else conf
        self.__iplist = conf.pop('ip', None) or []
        self.__conf = conf
        self.__logger = logging.getLogger('blocker')

    def doFilter(self, peer:dict[str|bool|int|float]):
        for key, rules in self.__conf.items():
            if key not in peer:
                continue
            data = peer[key]
            for rule in rules:
                if self.doRuleFilter(rule, data):
                    self.__logger.debug('封禁条件满足: %s => %s', data, rule)
                    return True
        return False
