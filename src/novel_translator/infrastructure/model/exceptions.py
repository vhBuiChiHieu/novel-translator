class ModelProviderError(Exception):
    pass


class ModelTimeoutError(ModelProviderError):
    pass


class ModelConnectionError(ModelProviderError):
    pass


class ModelInvalidResponseError(ModelProviderError):
    pass
