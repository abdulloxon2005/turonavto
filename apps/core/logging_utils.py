import json
import logging


class JsonFormatter(logging.Formatter):
    """Strukturalangan (JSON) log formatlagich."""

    def format(self, record):
        payload = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        for key in ('user_id', 'request_id', 'ip'):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)
