import json
import os
from functools import lru_cache

# 定义权限类别映射（与permission_analysis.py保持一致）
PERMISSION_MAPPING = {
    'Location': ['Location',
                 'Geolocation',
                 'GPS',
                 'Place',
                 'Address',
                 'Coordinates'],
    'Contacts': ['Contacts',
                 'Address Book',
                 'People',
                 'Phonebook',
                 'Contact List',
                 'Contact Details'],
    'Phone': ['Device or other IDs',
              'IMEI',
              'SIM Serial',
              'Phone Number',
              'Line 1 Number',
              'Network Country ISO',
              'Network Operator',
              'Subscriber ID',
              'Wi-Fi connection information',
              'Bluetooth MAC Address',
              'Cellular Network Info',
              'Phone Calls',
              'Call Log',
              'Call History',
              'Personal info',
              'App activity',
              'App info and performance'],
    'SMS': ['Messages',
            'SMS',
            'MMS',
            'Text Messages',
            'Call Log',
            'Call History',
            'SMS/MMS'],
    'Storage': ['Photos and videos',
                'Files and docs',
                'Photos/Media/Files',
                'Document Files',
                'Media Files',
                'Internal Storage',
                'External Storage',
                'SD Card Access',
                'Storage',
                'Financial info',
                'Audio files',
                'Web browsing'],
    'Camera': ['Photos and videos',
               'Camera',
               'Take Photos',
               'Take Videos',
               'Camera Metadata',
               'Image Capture',
               'Video Capture',
               'Camera Access'],
    'Microphone': ['Audio',
                   'Microphone',
                   'Voice Recording',
                   'Sound Input',
                   'Audio Capture',
                   'Microphone Access'],
    'Calendar': ['Calendar',
                 'Events',
                 'Reminders',
                 'Calendar Events',
                 'Calendar Access',
                 'Calendar Data'],
    'Sensors': ['Sensors',
                'Sensor Data',
                'Accelerometer',
                'Gyroscope',
                'Magnetometer',
                'Light Sensor',
                'Proximity Sensor',
                'Barometer',
                'Humidity Sensor',
                'Temperature Sensor',
                'Sensor Access',
                'Health and fitness']
}

# 反向映射，用于快速查找数据项对应的权限类别
REVERSE_MAPPING = {}
for permission, items in PERMISSION_MAPPING.items():
    for item in items:
        if item not in REVERSE_MAPPING:
            REVERSE_MAPPING[item] = []
        REVERSE_MAPPING[item].append(permission)

# 定义渠道映射
CHANNELS = {
    'data_collected': '渠道一',
    'permission': '渠道二',
    'security_practices': '渠道三'
}

# 定义九个权限类别
PERMISSION_CATEGORIES = list(PERMISSION_MAPPING.keys())

# 使用缓存优化的辅助函数
@lru_cache(maxsize=None)
def _map_single_item(item):
    if item in REVERSE_MAPPING:
        return set(REVERSE_MAPPING[item])
    # 特殊处理'App info and performance'
    elif item == 'App info and performance':
        return set()
    # 对于传感器相关项
    elif 'sensors' in item.lower() or 'sensor' in item.lower():
        return {'Sensors'}
    return set()

# 主映射函数
def map_to_permissions(data_items):
    permissions = set()
    for item in data_items:
        permissions.update(_map_single_item(item))
    return permissions


def load_json_data(file_path):
    """加载JSON数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误: 文件 {file_path} 不存在")
        return []
    except json.JSONDecodeError:
        print(f"错误: 文件 {file_path} 不是有效的JSON格式")
        return []


def analyze_permissions(app_data):
    """分析应用数据，生成权限三元组"""
    results = []

    app_info = {
        'app_name': app_data.get('name', 'unknown'),
        'app_id': app_data.get('_id', 'unknown'),
        'genre': app_data.get('genre', 'unknown')
    }

    for channel_field, channel_name in CHANNELS.items():
        # 初始化权限存在情况为0（不存在）
        permission_status = {cat: 0 for cat in PERMISSION_CATEGORIES}
        # 标记是否有矛盾
        has_conflict = {cat: False for cat in PERMISSION_CATEGORIES}

        # 检查字段是否存在
        if channel_field not in app_data:
            # 字段不存在，所有权限都标记为0
            for cat in PERMISSION_CATEGORIES:
                results.append((app_info, channel_name, cat, 0))
            continue

        field_value = app_data[channel_field]

        # 处理列表类型的字段
        if isinstance(field_value, list):
            # 存储每个权限类别对应的原始数据项
            permission_items = {cat: [] for cat in PERMISSION_CATEGORIES}
            for item in field_value:
                categories = _map_single_item(item)
                for category in categories:
                    permission_items[category].append(item)
                    # 如果已经标记为存在，现在又发现存在，不改变状态
                    # 如果之前未标记，现在标记为存在
                    if permission_status[category] == 0:
                        permission_status[category] = 1
                    # 如果之前标记为不存在，现在发现存在，标记为矛盾
                    elif permission_status[category] == -1:
                        has_conflict[category] = True

            # 检查是否有矛盾
            for cat in PERMISSION_CATEGORIES:
                if has_conflict[cat]:
                    results.append((app_info, channel_name, cat, -1))
                else:
                    results.append((app_info, channel_name, cat, permission_status[cat]))
        else:
            # 非列表类型字段，直接检查
            categories = _map_single_item(str(field_value))
            for category in categories:
                results.append((app_info, channel_name, category, 1))
            # 对于其他未匹配的权限类别，标记为0
            for cat in PERMISSION_CATEGORIES:
                if cat not in categories:
                    results.append((app_info, channel_name, cat, 0))

    return results


def process_app_database(file_path):
    """处理应用数据库，生成所有应用的权限三元组"""
    apps_data = load_json_data(file_path)
    if not apps_data:
        return []

    all_results = []
    for app in apps_data:
        app_id = app.get('_id', 'unknown')
        app_name = app.get('name', 'unknown')
        print(f"处理应用: {app_name} ({app_id})")
        
        app_results = analyze_permissions(app)
        all_results.extend(app_results)

    return all_results


def save_results(results, output_file):
    """保存结果到文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入CSV表头
        f.write("应用名称,应用ID,应用类别,渠道,权限,是否存在该权限\n")
        
        # 按应用分组输出
        app_results = {}
        for result in results:
            app_info, channel, permission, status = result
            app_key = (app_info['app_name'], app_info['app_id'], app_info['genre'])
            if app_key not in app_results:
                app_results[app_key] = []
            app_results[app_key].append((channel, permission, status))
        
        # 遍历每个应用并输出
        for idx, (app_key, triples) in enumerate(app_results.items()):
            app_name, app_id, genre = app_key
            
            # 应用信息
            f.write(f"应用名称: {app_name}\n")
            f.write(f"应用ID: {app_id}\n")
            f.write(f"应用类别: {genre}\n")
            f.write("权限三元组:\n")
            
            # 输出该应用的所有三元组
            for channel, permission, status in triples:
                f.write(f"{channel},{permission},{status}\n")
            
            # 在应用之间添加分隔线 (除了最后一个应用)
            if idx < len(app_results) - 1:
                f.write("--------------------------------------------------\n")
    print(f"结果已保存到 {output_file}")


def main():
    # 定义文件路径
    input_file = 'app_database.json'
    output_file = 'permission_triples.txt'

    # 处理数据
    results = process_app_database(input_file)

    # 保存结果
    if results:
        save_results(results, output_file)
        print(f"共生成 {len(results)} 个权限三元组")
    else:
        print("未生成任何权限三元组")


if __name__ == '__main__':
    main()