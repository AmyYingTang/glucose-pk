"""
CGM Provider 抽象层
支持多种血糖监测设备（Dexcom、Abbott Libre 等）
"""

from .base import BaseCGMProvider, CGMReading
from .dexcom import DexcomProvider
from .libre import LibreProvider

# 支持的设备类型
PROVIDER_TYPES = {
    'dexcom': {
        'class': DexcomProvider,
        'name': 'Dexcom G6/G7',
        'description': '需要 Dexcom 账户用户名和密码',
        'fields': [
            {'name': 'username', 'label': '用户名/邮箱', 'type': 'text', 'required': True},
            {'name': 'password', 'label': '密码', 'type': 'password', 'required': True},
            {'name': 'region', 'label': '地区', 'type': 'select', 'required': False,
             'options': [
                 {'value': 'us', 'label': '美国'},
                 {'value': 'ous', 'label': '非美国（国际）'}
             ],
             'default': 'ous'}
        ]
    },
    'libre': {
        'class': LibreProvider,
        'name': 'FreeStyle Libre',
        'description': '需要 LibreLinkUp 账户邮箱和密码',
        'fields': [
            {'name': 'username', 'label': '邮箱', 'type': 'email', 'required': True},
            {'name': 'password', 'label': '密码', 'type': 'password', 'required': True},
            {'name': 'region', 'label': '地区', 'type': 'select', 'required': False,
             'options': [
                 {'value': 'ap', 'label': '亚太（中国大陆）'},
                 {'value': 'eu', 'label': '欧洲'},
                 {'value': 'us', 'label': '美国'},
                 {'value': 'au', 'label': '澳大利亚'},
                 {'value': 'jp', 'label': '日本'},
                 {'value': 'de', 'label': '德国'},
                 {'value': 'fr', 'label': '法国'},
                 {'value': 'ca', 'label': '加拿大'},
             ],
             'default': 'ap'}
        ]
    }
}


def get_provider(device_type: str, credentials: dict) -> BaseCGMProvider:
    """
    根据设备类型创建 Provider 实例
    
    Args:
        device_type: 设备类型 ('dexcom', 'libre')
        credentials: 凭证字典
    
    Returns:
        BaseCGMProvider 实例
    """
    if device_type not in PROVIDER_TYPES:
        raise ValueError(f"不支持的设备类型: {device_type}")
    
    provider_class = PROVIDER_TYPES[device_type]['class']
    return provider_class(credentials)


def get_supported_devices() -> list:
    """获取支持的设备类型列表（用于前端展示）"""
    return [
        {
            'type': device_type,
            'name': info['name'],
            'description': info['description'],
            'fields': info['fields']
        }
        for device_type, info in PROVIDER_TYPES.items()
    ]
