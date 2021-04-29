import lxml.html
import lxml.etree
import pandas as pd
import logging
import os.path


def read_history():
    if os.path.isfile('watch_history.pkl'):
        watch_history_df = pd.read_pickle('watch_history.pkl')
        return watch_history_df

    with open('Takeout/YouTube and YouTube Music/history/watch-history.html', mode='r') as f:
        content = f.read()
        html_doc = lxml.html.fromstring(content)

    video_records = html_doc.xpath('//div[@class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1"]')
    print(len(video_records))

    times, titles, IDs = [], [], []
    for i, video in enumerate(video_records):
        if 'Watched a video that has been removed' in lxml.etree.tostring(video).decode('utf-8'):
            logging.warning(f"{i}-th video has been removed.")
            continue
        else:
            times.append(video.xpath('./a[last()]/following-sibling::text()[normalize-space(.) != ""][1]')[0])
            IDs.append(video.xpath('./a[1]/@href')[0].split("=")[1])
            titles.append(video.xpath('./a[1]/text()[1]')[0])

    watch_history_df = pd.DataFrame({
        'video_title': titles,
        'watched_time': times,
        'id': IDs
    })

    watch_history_df.to_pickle('watch_history.pkl')
    return watch_history_df


import requests


# example: call_api('SG2pDkdu5kE')
def call_api(video_id, key='AIzaSyDZ-0MjJmVaKrMqFvFordRKoF-plQtRzPo'):
    url = f'https://www.googleapis.com/youtube/v3/videos?id={video_id}&key={key}&part' \
          f'=snippet&fields=items(id,snippet(channelId,title,categoryId))'
    response = requests.get(url)
    # TODO what if request fails
    return response


def retrieve_meta_data():
    if os.path.isfile('metadata.pkl'):
        metadata = pd.read_pickle('metadata.pkl')
        return metadata

    watched = read_history()
    IDs = watched['id']

    unique_IDs = set(IDs)

    ids, channel_ids, titles, category_ids = [], [], [], []

    for id_ in unique_IDs:
        response = call_api(id_)
        if response.status_code != 200:
            logging.error(f'fail to query metadate of the video {id_}')
            continue
        info = response.json().get('items')
        assert len(info) <= 1
        if len(info) == 0:
            logging.warning(f'the video {id_} has no metadata.')
            continue

        info = info[0]
        ids.append(info.get('id'))
        assert info.get('id').lower() == id_.lower()
        channel_ids.append(info.get('snippet').get('channelId'))
        titles.append(info.get('snippet').get('title'))
        category_ids.append(info.get('snippet').get('categoryId'))

    metadata = pd.DataFrame(
        {
            'id': ids,
            'channelId': channel_ids,
            'title': titles,
            'categoryId': category_ids
        }
    )

    metadata.to_pickle('metadata.pkl')
    return metadata


# TODO why there is no id between 3-9?
def retrieve_category_info(key='AIzaSyDZ-0MjJmVaKrMqFvFordRKoF-plQtRzPo'):
    if os.path.isfile('category.pkl'):
        return pd.read_pickle('category.pkl')

    # TODO regionCode ?
    api = f'https://www.googleapis.com/youtube/v3/videoCategories?key={key}&part=snippet&regionCode=UK'
    response = requests.get(api)
    items = response.json().get('items')

    ids, names = [], []
    for item in items:
        ids.append(item.get('id'))
        names.append(item.get('snippet').get('title'))

    category_info = pd.DataFrame({
        'categoryId': ids,
        'categoryName': names
    })

    category_info.to_pickle('category.pkl')
    return category_info


raw_history = read_history()
raw_metadata = retrieve_meta_data()
category_info = retrieve_category_info()

metadata = pd.merge(raw_metadata, category_info, on="categoryId")
print(metadata)

history = pd.merge(raw_history, metadata, on="id")

# todo better way
history['watched_time'] = history['watched_time'].apply(func=lambda x:' '.join(x.split(',')[0].split(' ')[1:3]))
history['watched_time'] = history['watched_time'].astype('datetime64[ns]')

import matplotlib
import matplotlib.pyplot as plt
from collections import defaultdict

matplotlib.use('TkAgg')
by_category = history.groupby(['watched_time', 'categoryName']).size().to_frame('total_number').reset_index()
print(by_category)


all_categories = set(by_category['categoryName'])
all_watched_time = [x for x in set(by_category['watched_time'])]
all_watched_time.sort()
counts_of_category = defaultdict(list)

for category in all_categories:
    for time in all_watched_time:
        selected = by_category.loc[by_category['watched_time']==time].loc[by_category['categoryName']==category]
        if len(selected) > 0:
            assert len(selected) == 1
            counts_of_category[category].append(selected.head(1)['total_number'].iloc[0])
        else:
            counts_of_category[category].append(0)

print(counts_of_category)

counts_of_category_df = pd.DataFrame(counts_of_category, index=all_watched_time)
# counts_of_category_df['watched_time'] = all_watched_time
print(counts_of_category_df)
counts_of_category_df.plot.area(stacked=True)
counts_of_category_df.plot.area(stacked=False)



plt.show()

