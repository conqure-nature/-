import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict, Counter

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# Android官方定义的危险权限
ANDROID_DANGEROUS_PERMISSIONS = {
    'Location': True,
    'Contacts': True,
    'Phone': True,
    'SMS': True,
    'Storage': True,
    'Camera': True,
    'Microphone': True,
    'Calendar': True,
    'Sensors': True  # 部分传感器权限属于危险权限
}

# 权限敏感度映射 (1-5，5为最高敏感)
PERMISSION_SENSITIVITY = {
    'Location': 5,
    'Contacts': 5,
    'Phone': 5,
    'SMS': 5,
    'Storage': 4,
    'Camera': 4,
    'Microphone': 4,
    'Calendar': 3,
    'Sensors': 3
}


def load_triple_data(file_path):
    """加载权限三元组数据"""
    apps_data = []
    current_app = {}
    triples = []
    header = None

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        # 跳过CSV表头
        if lines and ',' in lines[0]:
            lines = lines[1:]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('应用名称:'):
                # 如果已有当前应用数据，先保存
                if current_app and triples:
                    current_app['triples'] = triples
                    apps_data.append(current_app)
                    triples = []
                
                # 开始新应用
                current_app = {
                    'app_name': line.replace('应用名称:', '').strip(),
                    'app_id': '',
                    'genre': ''
                }
            elif line.startswith('应用ID:'):
                current_app['app_id'] = line.replace('应用ID:', '').strip()
            elif line.startswith('应用类别:'):
                current_app['genre'] = line.replace('应用类别:', '').strip()
            elif line.startswith('权限三元组:'):
                continue
            elif line.startswith('---'):
                # 应用结束，保存数据
                if current_app and triples:
                    current_app['triples'] = triples
                    apps_data.append(current_app)
                    current_app = {}
                    triples = []
            elif ',' in line:
                # 解析三元组
                parts = line.split(',')
                if len(parts) == 3:
                    channel, permission, status = parts
                    try:
                        status = int(status)
                        triples.append({
                            'channel': channel,
                            'permission': permission,
                            'status': status
                        })
                    except ValueError:
                        continue
    
    # 保存最后一个应用
    if current_app and triples:
        current_app['triples'] = triples
        apps_data.append(current_app)
    
    return apps_data


def analyze_permission_frequency(apps_data):
    """权限使用频率分析"""
    # 统计所有应用中收集次数最多的权限
    permission_counter = Counter()
    for app in apps_data:
        for triple in app['triples']:
            # 只统计渠道一中状态为1的权限（表示收集）
            if triple['channel'] == '渠道一' and triple['status'] == 1:
                permission_counter[triple['permission']] += 1
    
    # 排序并返回前N个高频权限
    top_permissions = permission_counter.most_common(10)
    
    # 高风险权限集群（敏感权限且使用频率高）
    high_risk_permissions = []
    for permission, count in permission_counter.items():
        if PERMISSION_SENSITIVITY.get(permission, 0) >= 4 and count > 10:
            high_risk_permissions.append((permission, count))
    
    return {
        'top_permissions': top_permissions,
        'high_risk_permissions': high_risk_permissions,
        'all_permissions_count': permission_counter
    }


def analyze_dangerous_permissions(apps_data):
    """分析危险权限占比"""
    total_dangerous = 0
    total_collected = 0
    
    for app in apps_data:
        for triple in app['triples']:
            if triple['channel'] == '渠道一' and triple['status'] == 1:
                total_collected += 1
                if ANDROID_DANGEROUS_PERMISSIONS.get(triple['permission'], False):
                    total_dangerous += 1
    
    dangerous_ratio = (total_dangerous / total_collected) * 100 if total_collected > 0 else 0
    
    return {
        'dangerous_ratio': dangerous_ratio,
        'total_dangerous': total_dangerous,
        'total_collected': total_collected
    }


def analyze_channel_consistency(apps_data):
    """分析渠道间一致性"""
    # 三重一致性验证
    triple_consistent_count = 0
    total_permissions = 0
    
    # 按权限分组统计一致性
    permission_consistency = defaultdict(lambda: {'consistent': 0, 'total': 0})
    
    # 应用级一致性
    app_consistency = []
    
    for app in apps_data:
        app_name = app['app_name']
        app_triples = app['triples']
        
        # 按权限分组
        permission_channels = defaultdict(dict)
        for triple in app_triples:
            channel = triple['channel']
            permission = triple['permission']
            status = triple['status']
            permission_channels[permission][channel] = status
        
        # 计算应用级一致性
        app_consistent = 0
        app_total = 0
        
        for permission, channels in permission_channels.items():
            total_permissions += 1
            permission_consistency[permission]['total'] += 1
            app_total += 1
            
            # 检查三个渠道是否都存在且状态一致
            if len(channels) == 3:
                statuses = list(channels.values())
                if all(s == statuses[0] for s in statuses) and statuses[0] != -1:
                    triple_consistent_count += 1
                    permission_consistency[permission]['consistent'] += 1
                    app_consistent += 1
        
        # 计算应用级一致性比例
        if app_total > 0:
            app_consistency.append({
                'app_name': app_name,
                'consistency_ratio': (app_consistent / app_total) * 100
            })
    
    # 计算总体三重一致性比例
    triple_consistency_ratio = (triple_consistent_count / total_permissions) * 100 if total_permissions > 0 else 0
    
    # 计算每个权限的一致性比例
    for permission in permission_consistency:
        data = permission_consistency[permission]
        data['ratio'] = (data['consistent'] / data['total']) * 100 if data['total'] > 0 else 0
    
    return {
        'triple_consistency_ratio': triple_consistency_ratio,
        'permission_consistency': permission_consistency,
        'app_consistency': app_consistency
    }


def prepare_heatmap_data(apps_data):
    """准备热力图数据：权限使用频率 vs 敏感度"""
    # 统计权限使用频率
    permission_counter = Counter()
    for app in apps_data:
        for triple in app['triples']:
            if triple['channel'] == '渠道一' and triple['status'] == 1:
                permission_counter[triple['permission']] += 1
    
    # 准备热力图数据
    heatmap_data = []
    for permission in PERMISSION_SENSITIVITY:
        frequency = permission_counter.get(permission, 0)
        sensitivity = PERMISSION_SENSITIVITY[permission]
        
        # 归一化频率 (0-1)
        max_freq = max(permission_counter.values()) if permission_counter else 1
        normalized_freq = frequency / max_freq
        
        heatmap_data.append({
            'permission': permission,
            'frequency': frequency,
            'sensitivity': sensitivity,
            'normalized_freq': normalized_freq
        })
    
    return pd.DataFrame(heatmap_data)


def prepare_sankey_data(apps_data):
    """准备桑基图数据：权限流动路径"""
    # 统计渠道间权限状态变化
    flow_counts = defaultdict(int)
    
    for app in apps_data:
        # 按权限和应用分组
        permission_status = defaultdict(dict)
        for triple in app['triples']:
            permission_status[triple['permission']][triple['channel']] = triple['status']
        
        # 检查三个渠道的状态
        for permission, channels in permission_status.items():
            if '渠道一' in channels and '渠道二' in channels and '渠道三' in channels:
                flow_key = (
                    channels['渠道一'],
                    channels['渠道二'],
                    channels['渠道三']
                )
                flow_counts[flow_key] += 1
    
    # 准备桑基图数据
    labels = ['0', '1', '-1']
    source = []
    target = []
    value = []
    
    # 渠道一 -> 渠道二
    for (c1, c2, c3), count in flow_counts.items():
        # 确保标签存在
        for label in [str(c1), str(c2), str(c3)]:
            if label not in labels:
                labels.append(label)
        
        # 渠道一 -> 渠道二
        source.append(labels.index(str(c1)))
        target.append(labels.index(str(c2)) + 3)  # 偏移以区分不同渠道
        value.append(count)
        
        # 渠道二 -> 渠道三
        source.append(labels.index(str(c2)) + 3)
        target.append(labels.index(str(c3)) + 6)  # 再次偏移
        value.append(count)
    
    # 更新标签以表明渠道
    labels = ([f'渠道一: {l}' for l in labels[:3]] + 
              [f'渠道二: {l}' for l in labels[:3]] + 
              [f'渠道三: {l}' for l in labels[:3]])
    
    return {
        'labels': labels,
        'source': source,
        'target': target,
        'value': value
    }


def prepare_radar_data(apps_data, top_n=5):
    """准备雷达图数据：应用权限策略多维对比"""
    # 按应用类别分组
    genre_apps = defaultdict(list)
    for app in apps_data:
        genre_apps[app['genre']].append(app)
    
    # 选择应用数量最多的前N个类别
    top_genres = sorted(genre_apps.keys(), key=lambda x: len(genre_apps[x]), reverse=True)[:top_n]
    
    # 准备雷达图数据
    radar_data = []
    for genre in top_genres:
        apps = genre_apps[genre]
        
        # 统计该类别的权限使用情况
        permission_usage = defaultdict(int)
        total_apps = len(apps)
        
        for app in apps:
            for triple in app['triples']:
                if triple['channel'] == '渠道一' and triple['status'] == 1:
                    permission_usage[triple['permission']] += 1
        
        # 计算每个权限的使用比例
        for permission in PERMISSION_SENSITIVITY:
            usage_ratio = (permission_usage.get(permission, 0) / total_apps) * 100
            radar_data.append({
                'genre': genre,
                'permission': permission,
                'usage_ratio': usage_ratio
            })
    
    return pd.DataFrame(radar_data)


def prepare_genre_comparison_data(apps_data):
    """准备同类应用权限策略差异数据"""
    # 按应用类别分组
    genre_apps = defaultdict(list)
    for app in apps_data:
        genre_apps[app['genre']].append(app)
    
    # 选择应用数量较多的类别
    comparison_data = []
    for genre, apps in genre_apps.items():
        if len(apps) < 5:  # 至少需要5个应用进行比较
            continue
        
        # 统计每个应用的权限使用情况
        app_permissions = {}
        for app in apps:
            app_name = app['app_name']
            permissions = set()
            for triple in app['triples']:
                if triple['channel'] == '渠道一' and triple['status'] == 1:
                    permissions.add(triple['permission'])
            app_permissions[app_name] = permissions
        
        # 计算权限交集和并集
        all_permissions = set.union(*app_permissions.values()) if app_permissions else set()
        common_permissions = set.intersection(*app_permissions.values()) if len(app_permissions) > 1 else all_permissions
        
        comparison_data.append({
            'genre': genre,
            'app_count': len(apps),
            'common_permissions': common_permissions,
            'common_count': len(common_permissions),
            'total_permissions': len(all_permissions),
            'common_ratio': (len(common_permissions) / len(all_permissions)) * 100 if all_permissions else 0
        })
    
    return comparison_data


def visualize_permission_frequency(top_permissions, output_file='viz_permission_frequency.png'):
    """可视化权限使用频率"""
    permissions, counts = zip(*top_permissions)
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=list(permissions), y=list(counts), palette='viridis')
    plt.title('应用收集次数最多的权限Top 10')
    plt.xlabel('权限类别')
    plt.ylabel('收集次数')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f'权限使用频率图已保存为 {output_file}')


def visualize_dangerous_permissions(dangerous_ratio, output_file='viz_dangerous_permissions.png'):
    """可视化危险权限占比"""
    labels = ['危险权限', '非危险权限']
    sizes = [dangerous_ratio, 100 - dangerous_ratio]
    colors = ['red', 'green']
    
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.axis('equal')  # 确保饼图是圆的
    plt.title('危险权限占总收集权限的比例')
    plt.savefig(output_file)
    plt.close()
    print(f'危险权限占比图已保存为 {output_file}')


def visualize_channel_consistency(consistency_data, output_file='viz_channel_consistency.png'):
    """可视化渠道间一致性"""
    # 权限一致性条形图
    permission_consistency = consistency_data['permission_consistency']
    permissions = list(permission_consistency.keys())
    ratios = [permission_consistency[p]['ratio'] for p in permissions]
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=permissions, y=ratios, palette='coolwarm')
    plt.title('各权限的渠道间一致性比例')
    plt.xlabel('权限类别')
    plt.ylabel('一致性比例 (%)')
    plt.xticks(rotation=45)
    plt.axhline(y=consistency_data['triple_consistency_ratio'], color='r', linestyle='--', label=f'总体一致性: {consistency_data["triple_consistency_ratio"]:.1f}%')
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f'渠道间一致性图已保存为 {output_file}')


def visualize_heatmap(heatmap_df, output_file='viz_permission_heatmap.png'):
    """可视化权限使用频率 vs 敏感度热力图"""
    # 重塑数据为矩阵形式
    heatmap_matrix = heatmap_df.pivot(index='permission', columns='sensitivity', values='normalized_freq')
    
    plt.figure(figsize=(12, 8))
    sns.heatmap(heatmap_matrix, annot=True, cmap='YlOrRd', fmt='.2f')
    plt.title('权限使用频率 vs 敏感度热力图')
    plt.xlabel('敏感度 (1-5)')
    plt.ylabel('权限类别')
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f'权限热力图已保存为 {output_file}')


def visualize_sankey(sankey_data, output_file='viz_permission_sankey.html'):
    """可视化权限流动路径桑基图"""
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=sankey_data['labels']
        ),
        link=dict(
            source=sankey_data['source'],
            target=sankey_data['target'],
            value=sankey_data['value']
        )
    )])

    fig.update_layout(title_text="权限状态流动路径 (渠道一→渠道二→渠道三)", font_size=10)
    fig.write_html(output_file)
    print(f'权限桑基图已保存为 {output_file}')


def visualize_radar(radar_df, output_file='viz_permission_radar.html'):
    """可视化应用权限策略雷达图"""
    fig = px.line_polar(radar_df, r='usage_ratio', theta='permission', color='genre', line_close=True)
    fig.update_layout(
        title='不同应用类别的权限策略对比',
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        )
    )
    fig.write_html(output_file)
    print(f'权限雷达图已保存为 {output_file}')


def visualize_genre_comparison(comparison_data, output_file='viz_genre_comparison.png'):
    """可视化同类应用权限策略差异"""
    genres = [item['genre'] for item in comparison_data]
    common_ratios = [item['common_ratio'] for item in comparison_data]
    
    plt.figure(figsize=(12, 6))
    sns.barplot(x=genres, y=common_ratios, palette='magma')
    plt.title('同类应用权限策略的一致性比例')
    plt.xlabel('应用类别')
    plt.ylabel('同类应用共同权限比例 (%)')
    plt.xticks(rotation=45)
    plt.axhline(y=50, color='r', linestyle='--', label='50% 参考线')
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f'同类应用权限对比图已保存为 {output_file}')


def main():
    # 加载数据
    input_file = 'permission_triples.txt'
    print(f'正在加载数据: {input_file}')
    apps_data = load_triple_data(input_file)
    print(f'成功加载 {len(apps_data)} 个应用的数据')
    
    # 1. 权限使用频率分析
    print('正在进行权限使用频率分析...')
    freq_result = analyze_permission_frequency(apps_data)
    visualize_permission_frequency(freq_result['top_permissions'], 'viz_permission_frequency.png')
    print(f'高频使用权限: {freq_result["top_permissions"]}')
    print(f'高风险权限集群: {freq_result["high_risk_permissions"]}')
    
    # 2. 危险权限分析
    print('正在进行危险权限分析...')
    dangerous_result = analyze_dangerous_permissions(apps_data)
    visualize_dangerous_permissions(dangerous_result['dangerous_ratio'], 'viz_dangerous_permissions.png')
    print(f'危险权限占比: {dangerous_result["dangerous_ratio"]:.2f}%')
    
    # 3. 渠道一致性分析
    print('正在进行渠道一致性分析...')
    consistency_result = analyze_channel_consistency(apps_data)
    visualize_channel_consistency(consistency_result, 'viz_channel_consistency.png')
    print(f'三重渠道一致性比例: {consistency_result["triple_consistency_ratio"]:.2f}%')
    
    # 4. 热力图
    print('正在准备热力图数据...')
    heatmap_df = prepare_heatmap_data(apps_data)
    visualize_heatmap(heatmap_df, 'viz_permission_heatmap.png')
    
    # 5. 桑基图
    print('正在准备桑基图数据...')
    sankey_data = prepare_sankey_data(apps_data)
    visualize_sankey(sankey_data, 'viz_permission_sankey.html')
    
    # 6. 雷达图
    print('正在准备雷达图数据...')
    radar_df = prepare_radar_data(apps_data)
    visualize_radar(radar_df, 'viz_permission_radar.html')
    
    # 7. 同类应用对比
    print('正在进行同类应用对比分析...')
    genre_comparison = prepare_genre_comparison_data(apps_data)
    visualize_genre_comparison(genre_comparison, 'viz_genre_comparison.png')
    
    print('所有分析和可视化已完成！')


if __name__ == '__main__':
    main()