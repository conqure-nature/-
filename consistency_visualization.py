import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict

# 设置中文字体
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

def load_triple_data(file_path):
    """加载权限三元组数据"""
    apps_data = []
    current_app = {}
    triples = []
    header = None

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        # 解析CSV表头
        if lines and ',' in lines[0]:
            header = lines[0].strip().split(',')
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

def calculate_metrics(apps_data):
    """计算所有指标"""
    # 1. 总体一致性覆盖度(OCC)计算
    # OCC定义：所有应用中，三个渠道权限状态一致的比例
    all_permissions_count = 0
    consistent_count = 0
    apps_occ = []
    
    # 2. 按应用类别统计OCC
    genre_occ = defaultdict(lambda: {'count': 0, 'consistent': 0})
    
    # 3. 跨渠道遗漏(CCOR)：渠道一(数据收集)存在但渠道二(权限申请)缺失的权限比例
    ccor_data = defaultdict(lambda: {'total': 0, 'missing': 0})
    
    # 4. 跨渠道矛盾(CCCR)：渠道一和渠道三明确矛盾的情况
    cccr_data = defaultdict(lambda: {'total': 0, 'conflict': 0})
    
    # 5. 内部矛盾(ICA)：单个渠道内存在矛盾的情况
    ica_count = 0
    ica_by_genre = defaultdict(int)
    total_permissions = 0
    
    for app_idx, app in enumerate(apps_data):
        app_genre = app['genre']
        app_triples = app['triples']
        
        # 按权限和渠道分组
        permission_channels = defaultdict(dict)
        for triple in app_triples:
            channel = triple['channel']
            permission = triple['permission']
            status = triple['status']
            
            # 检查内部矛盾
            if channel in permission_channels[permission]:
                # 如果同一渠道同一权限已经有记录且状态不同
                if permission_channels[permission][channel] != status:
                    ica_count += 1
                    ica_by_genre[app_genre] += 1
            permission_channels[permission][channel] = status
            
            total_permissions += 1
        
        # 计算应用级OCC
        app_consistent = 0
        app_total = len(permission_channels)
        
        for permission, channels in permission_channels.items():
            # 检查三个渠道是否都存在且状态一致
            if len(channels) == 3:
                statuses = list(channels.values())
                if all(s == statuses[0] for s in statuses) and statuses[0] != -1:
                    app_consistent += 1
                    consistent_count += 1
                
                # 计算CCOR (渠道一存在但渠道二缺失)
                if '渠道一' in channels and '渠道二' in channels:
                    ccor_data[app_genre]['total'] += 1
                    if channels['渠道一'] == 1 and channels['渠道二'] == 0:
                        ccor_data[app_genre]['missing'] += 1
                
                # 计算CCCR (渠道一和渠道三明确矛盾)
                if '渠道一' in channels and '渠道三' in channels:
                    cccr_data[app_genre]['total'] += 1
                    if (channels['渠道一'] == 1 and channels['渠道三'] == 0) or \
                       (channels['渠道一'] == 0 and channels['渠道三'] == 1):
                        cccr_data[app_genre]['conflict'] += 1
            
            all_permissions_count += 1
        
        # 计算应用级OCC
        if app_total > 0:
            app_occ = app_consistent / app_total * 100
            apps_occ.append(app_occ)
            
            # 更新类别OCC
            genre_occ[app_genre]['count'] += app_total
            genre_occ[app_genre]['consistent'] += app_consistent
    
    # 计算总体OCC趋势
    overall_occ_trend = []
    cumulative_consistent = 0
    cumulative_total = 0
    for i, app_occ in enumerate(apps_occ):
        # 假设每个应用贡献相同数量的权限
        app_consistent = int(app_occ / 100 * len(permission_channels))
        cumulative_consistent += app_consistent
        cumulative_total += len(permission_channels)
        overall_occ = cumulative_consistent / cumulative_total * 100 if cumulative_total > 0 else 0
        overall_occ_trend.append(overall_occ)
    
    # 计算类别级OCC
    genre_occ_result = {}
    for genre, data in genre_occ.items():
        if data['count'] > 0:
            genre_occ_result[genre] = data['consistent'] / data['count'] * 100
        else:
            genre_occ_result[genre] = 0
    
    # 计算类别级CCOR
    ccor_result = {}
    for genre, data in ccor_data.items():
        if data['total'] > 0:
            ccor_result[genre] = data['missing'] / data['total'] * 100
        else:
            ccor_result[genre] = 0
    
    # 计算类别级CCCR
    cccr_result = {}
    for genre, data in cccr_data.items():
        if data['total'] > 0:
            cccr_result[genre] = data['conflict'] / data['total'] * 100
        else:
            cccr_result[genre] = 0
    
    # 计算ICA比例
    ica_ratio = ica_count / total_permissions * 100 if total_permissions > 0 else 0
    
    return {
        'overall_occ_trend': overall_occ_trend,
        'genre_occ': genre_occ_result,
        'ccor': ccor_result,
        'cccr': cccr_result,
        'ica_ratio': ica_ratio,
        'ica_by_genre': ica_by_genre
    }

def visualize_overall_occ_trend(occ_trend):
    """可视化总体OCC趋势"""
    plt.figure(figsize=(12, 6))
    plt.plot(range(1, len(occ_trend) + 1), occ_trend, marker='o', linestyle='-', color='blue')
    plt.title('总体一致性覆盖度(OCC)趋势分析')
    plt.xlabel('应用数量')
    plt.ylabel('OCC (%)')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig('viz_occ_trend.png')
    plt.close()
    print('总体OCC趋势图已保存为 viz_occ_trend.png')

def visualize_genre_occ(genre_occ):
    """可视化按应用类别统计的OCC"""
    # 分组柱状图
    plt.figure(figsize=(12, 6))
    genres = list(genre_occ.keys())
    occ_values = list(genre_occ.values())
    
    sns.barplot(x=genres, y=occ_values, palette='viridis')
    plt.title('不同应用类别的一致性覆盖度(OCC)')
    plt.xlabel('应用类别')
    plt.ylabel('OCC (%)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('viz_genre_occ_bar.png')
    plt.close()
    print('应用类别OCC柱状图已保存为 viz_genre_occ_bar.png')
    
    # 雷达图
    # 为雷达图准备数据
    radar_data = pd.DataFrame({
        'category': genres,
        'OCC': occ_values
    })
    
    fig = px.line_polar(radar_data, r='OCC', theta='category', line_close=True)
    fig.update_layout(
        title='不同应用类别的一致性覆盖度(OCC)雷达图',
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        )
    )
    fig.write_html('viz_genre_occ_radar.html')
    print('应用类别OCC雷达图已保存为 viz_genre_occ_radar.html')

def visualize_ccor(ccor_data):
    """可视化跨渠道遗漏(CCOR)"""
    genres = list(ccor_data.keys())
    ccor_values = list(ccor_data.values())
    
    # 计算非遗漏比例
    non_ccor_values = [100 - val for val in ccor_values]
    
    plt.figure(figsize=(12, 6))
    
    # 堆叠柱状图
    plt.bar(genres, non_ccor_values, label='无遗漏', color='green')
    plt.bar(genres, ccor_values, bottom=non_ccor_values, label='有遗漏', color='red')
    
    plt.title('跨渠道遗漏(CCOR)分析')
    plt.xlabel('应用类别')
    plt.ylabel('比例 (%)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig('viz_ccor_stacked_bar.png')
    plt.close()
    print('CCOR堆叠柱状图已保存为 viz_ccor_stacked_bar.png')

def visualize_cccr(cccr_data):
    """可视化跨渠道矛盾(CCCR)"""
    plt.figure(figsize=(12, 6))
    genres = list(cccr_data.keys())
    cccr_values = list(cccr_data.values())
    
    sns.barplot(x=genres, y=cccr_values, palette='magma')
    plt.title('跨渠道矛盾(CCCR)分析')
    plt.xlabel('应用类别')
    plt.ylabel('矛盾比例 (%)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('viz_cccr_bar.png')
    plt.close()
    print('CCCR条形图已保存为 viz_cccr_bar.png')

def visualize_ica(ica_ratio, ica_by_genre):
    """可视化内部矛盾(ICA)"""
    # 饼图
    labels = ['无内部矛盾', '有内部矛盾']
    sizes = [100 - ica_ratio, ica_ratio]
    colors = ['blue', 'red']
    
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    plt.axis('equal')  # 确保饼图是圆的
    plt.title('内部矛盾(ICA)比例')
    plt.savefig('viz_ica_pie.png')
    plt.close()
    print('ICA饼图已保存为 viz_ica_pie.png')
    
    # 按类别条形图
    if ica_by_genre:
        plt.figure(figsize=(12, 6))
        genres = list(ica_by_genre.keys())
        ica_counts = list(ica_by_genre.values())
        
        sns.barplot(x=genres, y=ica_counts, palette='coolwarm')
        plt.title('不同应用类别的内部矛盾(ICA)数量')
        plt.xlabel('应用类别')
        plt.ylabel('矛盾数量')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('viz_ica_by_genre_bar.png')
        plt.close()
        print('类别ICA条形图已保存为 viz_ica_by_genre_bar.png')

def main():
    # 加载数据
    input_file = 'permission_triples.txt'
    print(f'正在加载数据: {input_file}')
    apps_data = load_triple_data(input_file)
    print(f'成功加载 {len(apps_data)} 个应用的数据')
    
    # 计算指标
    print('正在计算指标...')
    metrics = calculate_metrics(apps_data)
    print('指标计算完成')
    
    # 可视化1: 总体OCC趋势
    visualize_overall_occ_trend(metrics['overall_occ_trend'])
    
    # 可视化2: 按应用类别OCC
    visualize_genre_occ(metrics['genre_occ'])
    
    # 可视化3: 跨渠道遗漏(CCOR)
    visualize_ccor(metrics['ccor'])
    
    # 可视化4: 跨渠道矛盾(CCCR)
    visualize_cccr(metrics['cccr'])
    
    # 可视化5: 内部矛盾(ICA)
    visualize_ica(metrics['ica_ratio'], metrics['ica_by_genre'])
    
    print('所有可视化已完成！')

if __name__ == '__main__':
    main()