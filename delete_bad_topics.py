import sqlite3

db_path = 'database/bot_db.sqlite'

threads_to_delete = [
    1595, 1793, 1818, 1836, 1862, 1867, 1874, 1890, 1900, 1930, 1944, 1955, 1958, 
    1961, 1969, 1973, 1984, 1988, 2001, 2014, 2037, 2041, 2052, 2065, 2083, 2085, 
    2105, 2115, 2116, 2119, 2128, 2135, 2155, 2186, 2191, 2207, 2209, 2218, 2221, 
    2228, 2244, 2252, 2265, 2279, 2296, 2298, 2332, 2339, 2356, 2366, 2374, 2382, 
    2398, 2400, 2410, 2411, 2435, 2437, 2439, 2443, 2447, 2487, 2531, 2543, 2550, 
    2562, 2572, 2599, 2600, 2611, 2637, 2644, 2645, 2647, 2656, 2658, 2661, 2675, 
    2689, 2706, 2740, 2742, 2745, 2746, 2750, 2780, 2790, 2791, 2794, 2803, 2811, 
    2825, 2836, 2851, 2857, 2860, 2870, 2873, 2874, 2883, 2907, 2914, 2916, 2923, 
    2931, 2937, 2970, 2980, 2986, 2991, 2997, 3012, 3013, 3019, 3045, 3052, 3058, 
    3061, 3065, 3071, 3073, 3084, 3087, 3093, 3099, 3102, 3115, 3122, 3126, 3136, 
    3151, 3157, 3163, 3164, 3173
]

def main():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    deleted_bot_topics = 0
    deleted_topics = 0
    
    for thread_id in threads_to_delete:
        # Delete from bot_chat_topics
        c.execute("DELETE FROM bot_chat_topics WHERE thread_id = ?", (thread_id,))
        deleted_bot_topics += c.rowcount
        
        # Delete from topics
        c.execute("DELETE FROM topics WHERE thread_id = ?", (thread_id,))
        deleted_topics += c.rowcount
        
    conn.commit()
    conn.close()
    
    print(f"Deleted {deleted_bot_topics} entries from bot_chat_topics")
    print(f"Deleted {deleted_topics} entries from topics")

if __name__ == '__main__':
    main()
