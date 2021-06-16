
import streamlit as st
import json
import requests
import sys
import os
import pandas as pd
import numpy as np
import re
from datetime import datetime as dt
# for chart
pd.plotting.register_matplotlib_converters()
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns



st.set_page_config(layout="wide")

st.title('DataCracy ATOM Tiến Độ Lớp Học')
with open('env_variable.json','r') as j:
    json_data = json.load(j)

#SLACK_BEARER_TOKEN = os.environ.get('SLACK_BEARER_TOKEN') ## Get in setting of Streamlit Share
SLACK_BEARER_TOKEN = json_data['SLACK_BEARER_TOKEN']
DTC_GROUPS_URL = ('https://raw.githubusercontent.com/anhdanggit/atom-assignments/main/data/datacracy_groups.csv')
#st.write(json_data['SLACK_BEARER_TOKEN'])

@st.cache
def load_users_df():
    # Slack API User Data
    endpoint = "https://slack.com/api/users.list"
    headers = {"Authorization": "Bearer {}".format(json_data['SLACK_BEARER_TOKEN'])}
    response_json = requests.post(endpoint, headers=headers).json() 
    user_dat = response_json['members']

    # Convert to CSV
    user_dict = {'user_id':[],'name':[],'display_name':[],'real_name':[],'title':[],'is_bot':[]}
    for i in range(len(user_dat)):
      user_dict['user_id'].append(user_dat[i]['id'])
      user_dict['name'].append(user_dat[i]['name'])
      user_dict['display_name'].append(user_dat[i]['profile']['display_name'])
      user_dict['real_name'].append(user_dat[i]['profile']['real_name_normalized'])
      user_dict['title'].append(user_dat[i]['profile']['title'])
      user_dict['is_bot'].append(int(user_dat[i]['is_bot']))
    user_df = pd.DataFrame(user_dict) 
    # Read dtc_group hosted in github
    dtc_groups = pd.read_csv(DTC_GROUPS_URL)
    user_df = user_df.merge(dtc_groups, how='left', on='name')
    return user_df

@st.cache
def load_channel_df():
    endpoint2 = "https://slack.com/api/conversations.list"
    data = {'types': 'public_channel,private_channel'} # -> CHECK: API Docs https://api.slack.com/methods/conversations.list/test
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    response_json = requests.post(endpoint2, headers=headers, data=data).json() 
    channel_dat = response_json['channels']
    channel_dict = {'channel_id':[], 'channel_name':[], 'is_channel':[],'creator':[],'created_at':[],'topics':[],'purpose':[],'num_members':[]}
    for i in range(len(channel_dat)):
        channel_dict['channel_id'].append(channel_dat[i]['id'])
        channel_dict['channel_name'].append(channel_dat[i]['name'])
        channel_dict['is_channel'].append(channel_dat[i]['is_channel'])
        channel_dict['creator'].append(channel_dat[i]['creator'])
        channel_dict['created_at'].append(dt.fromtimestamp(float(channel_dat[i]['created'])))
        channel_dict['topics'].append(channel_dat[i]['topic']['value'])
        channel_dict['purpose'].append(channel_dat[i]['purpose']['value'])
        channel_dict['num_members'].append(channel_dat[i]['num_members'])
    channel_df = pd.DataFrame(channel_dict) 
    return channel_df

@st.cache(allow_output_mutation=True)
def load_msg_dict():
    endpoint3 = "https://slack.com/api/conversations.history"
    headers = {"Authorization": "Bearer {}".format(SLACK_BEARER_TOKEN)}
    msg_dict = {'channel_id':[],'msg_id':[], 'msg_ts':[], 'user_id':[], 'latest_reply':[],'reply_user_count':[],'reply_users':[],'github_link':[],'text':[]}
    for channel_id, channel_name in zip(channel_df['channel_id'], channel_df['channel_name']):
        print('Channel ID: {} - Channel Name: {}'.format(channel_id, channel_name))
        try:
            data = {"channel": channel_id} 
            response_json = requests.post(endpoint3, data=data, headers=headers).json()
            msg_ls = response_json['messages']
            for i in range(len(msg_ls)):
                if 'client_msg_id' in msg_ls[i].keys():
                    msg_dict['channel_id'].append(channel_id)
                    msg_dict['msg_id'].append(msg_ls[i]['client_msg_id'])
                    msg_dict['msg_ts'].append(dt.fromtimestamp(float(msg_ls[i]['ts'])))
                    msg_dict['latest_reply'].append(dt.fromtimestamp(float(msg_ls[i]['latest_reply'] if 'latest_reply' in msg_ls[i].keys() else 0))) ## -> No reply: 1970-01-01
                    msg_dict['user_id'].append(msg_ls[i]['user'])
                    msg_dict['reply_user_count'].append(msg_ls[i]['reply_users_count'] if 'reply_users_count' in msg_ls[i].keys() else 0)
                    msg_dict['reply_users'].append(msg_ls[i]['reply_users'] if 'reply_users' in msg_ls[i].keys() else 0) 
                    msg_dict['text'].append(msg_ls[i]['text'] if 'text' in msg_ls[i].keys() else 0) 
                    ## -> Censor message contains tokens
                    text = msg_ls[i]['text']
                    github_link = re.findall('(?:https?://)?(?:www[.])?github[.]com/[\w-]+/?', text)
                    msg_dict['github_link'].append(github_link[0] if len(github_link) > 0 else None)
        except:
            print('====> '+ str(response_json))
    msg_df = pd.DataFrame(msg_dict)
    return msg_df

def process_msg_data(msg_df, user_df, channel_df):
    ## Extract 2 reply_users
    msg_df['reply_user1'] = msg_df['reply_users'].apply(lambda x: x[0] if x != 0 else '')
    msg_df['reply_user2'] = msg_df['reply_users'].apply(lambda x: x[1] if x != 0 and len(x) > 1 else '')
    ## Merge to have a nice name displayed
    msg_df = msg_df.merge(user_df[['user_id','name','DataCracy_role']].rename(columns={'name':'submit_name'}), \
        how='left',on='user_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply1_name','user_id':'reply1_id'}), \
        how='left', left_on='reply_user1', right_on='reply1_id')
    msg_df = msg_df.merge(user_df[['user_id','name']].rename(columns={'name':'reply2_name','user_id':'reply2_id'}), \
        how='left', left_on='reply_user2', right_on='reply2_id')
    ## Merge for nice channel name
    msg_df = msg_df.merge(channel_df[['channel_id','channel_name','created_at']], how='left',on='channel_id')
    ## Format datetime cols
    msg_df['created_at'] = msg_df['created_at'].dt.strftime('%Y-%m-%d')
    msg_df['msg_date'] = msg_df['msg_ts'].dt.strftime('%Y-%m-%d')
    msg_df['msg_time'] = msg_df['msg_ts'].dt.strftime('%H:%M')
    msg_df['wordcount'] = msg_df.text.apply(lambda s: len(s.split()))
    return msg_df


# Table data
user_df = load_users_df()
channel_df = load_channel_df()
msg_df = load_msg_dict()

total = process_msg_data(msg_df, user_df, channel_df)

# table
# assignments 
as_total = total[total.channel_name.str.contains('assignment')]
as_total = as_total[as_total.DataCracy_role.str.contains('Learner')]
as_by_channel = as_total.groupby(by=(['user_id','submit_name','channel_id','channel_name']))['github_link'].nunique()
as_by_user = as_by_channel.groupby(by=(['user_id','submit_name'])).count()
as_by_user = as_by_user.sort_values(ascending=False)                                 
as_by_user = as_by_user.reset_index()


# wordcount
dis_total = total[total.channel_name.str.contains('discuss')]
dis_total = dis_total[dis_total.DataCracy_role.str.contains('Learner')]
user_wordcount = dis_total.groupby(by=(['user_id','submit_name'])).wordcount.sum()
user_wordcount = user_wordcount.sort_values(ascending=False)
user_wordcount = user_wordcount.reset_index()

# review
reviewed_total = as_total[(as_total.reply_users != 0) & \
                          ((as_total.reply_user1 != as_total.user_id) | (as_total.reply_user2 != as_total.user_id))]
reviewed_total=reviewed_total.loc[reviewed_total.groupby(by=(['user_id','submit_name','channel_id'])).msg_ts.idxmax()]
# reviewed_total = reviewed_total.reset_index().sort_values(by='channel_id',ascending=False)
# reviewed_total.rename(columns = {'channel_id':'no of be reviewed'})
reviewed_total = reviewed_total.groupby(by=(['user_id','submit_name'])).channel_id.nunique().reset_index()
reviewed_total = reviewed_total.rename(columns = {'channel_id':'time be reviewed'})

# merge
final = as_by_user.merge(user_wordcount, how='left',left_on=('user_id','submit_name'), right_on = ('user_id','submit_name'))
final = final.merge(reviewed_total, how='left',left_on=('user_id','submit_name'), right_on = ('user_id','submit_name'))
final = final.rename(columns={'github_link':'no of assignments'})
final['% be reviewed'] = final['time be reviewed']/final['no of assignments']*100
final['% be reviewed']=final['% be reviewed'].round(decimals=1)
final = final.sort_values(by='no of assignments',ascending=False)


# UI

option = st.selectbox(
    'Information about DATAcracy class',
     ('All','Top 5','Last 5'))

'You are viewing:', option
if option == 'All':
    st.write(final)
elif option == 'Top 5':
    st.write(final.head())
else:
    st.write(final.tail())

# distribution
st.markdown('Distribution')

agreea = st.button('Distribution of Number of assignments in class')
if agreea:
    figa,axa = plt.subplots()
    axa = sns.distplot(a=final['no of assignments'], kde=False)
    st.pyplot(figa)

agreew = st.button('Distribution of wordcount of assignments in class')
if agreew:
    figw,axw = plt.subplots()
    axw = sns.distplot(a=final['wordcount'], kde=False)
    st.pyplot(figw)   

agreep = st.button('Distribution of percentage of assignments reviewed of assignments in class')
if agreep:
    figp,axp = plt.subplots()
    axp = sns.distplot(a=final['% be reviewed'], kde=False)
    st.pyplot(figp)

agree2D = st.button('2D chart of number of assignments and time be reviewed')    
if agree2D:
    ax2D = sns.jointplot(x=final['no of assignments'], y=final['time be reviewed'], kind='kde')
    st.pyplot(ax2D)


# day and time
new_as_total=as_total.loc[as_total.groupby(by=(['user_id','submit_name','channel_id'])).msg_ts.idxmax()]
ts_time = new_as_total.msg_ts.reset_index()
ts_time['dayofweek'] = ts_time.msg_ts.dt.dayofweek
ts_time['day_name'] = ts_time.msg_ts.dt.day_name()
ts_time['hour'] = ts_time.msg_ts.dt.hour

# date

agreed = st.button('Distribution of day week submitted assignment')  
if agreed:
    figd,axd = plt.subplots()
    axd = sns.distplot(a=ts_time['dayofweek'], kde=False)
    axd.set_xticklabels(['','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
    for item in axd.get_xticklabels(): item.set_rotation(90)
    st.pyplot(figd)

agreeh = st.button('Distribution of hour submitted assignment')  
if agreeh:
    figh,axh = plt.subplots()
    axh = sns.distplot(a=ts_time['hour'], kde=False)
    plt.xticks([0,6, 12, 18, 24])
    st.pyplot(figh)


# cd OneDrive/Documents/GitHub/atom-assignments
## Run: streamlit run streamlit/datacracy_slack-thaole.py