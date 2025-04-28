import streamlit as st
import requests
from datetime import datetime
import xml.etree.ElementTree as ET
import re

BASE_URL = 'https://service.pbarmyff.com'
API_BASE = f'{BASE_URL}/api/cache'

# User-Agents for desktop and mobile
DESKTOP_UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/89.0.4389.82 Safari/537.36 Prerender (+https://github.com/prerender/prerender)'
MOBILE_UA = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.72 Mobile Safari/537.36 Prerender (+https://github.com/prerender/prerender)'

# Helper to trigger both variants
def trigger_both_variants(url):
    headers_desktop = {'User-Agent': DESKTOP_UA}
    headers_mobile = {'User-Agent': MOBILE_UA}
    errors = []
    try:
        resp1 = requests.get(f'{BASE_URL}/{url}', headers=headers_desktop)
        if resp1.status_code != 200:
            errors.append(f"Desktop: {resp1.status_code}")
    except Exception as e:
        errors.append(f"Desktop: {e}")
    try:
        resp2 = requests.get(f'{BASE_URL}/{url}', headers=headers_mobile)
        if resp2.status_code != 200:
            errors.append(f"Mobile: {resp2.status_code}")
    except Exception as e:
        errors.append(f"Mobile: {e}")
    return errors

st.set_page_config(page_title="Prerender Cache Manager", layout="wide")
st.title("Prerender Cache Manager")

# --- Sidebar Controls ---
st.sidebar.header("Cache Controls")

with st.sidebar.form(key="cache_url_form"):
    cache_url = st.text_input("URL to cache", "")
    submit_url = st.form_submit_button("Submit URL for Caching")
    if submit_url and cache_url:
        errors = trigger_both_variants(cache_url)
        if not errors:
            st.success("URL submitted for caching (desktop & mobile).")
        else:
            st.error("Errors: " + ", ".join(errors))

# --- Bulk Cache URLs ---
st.sidebar.markdown("---")
st.sidebar.subheader("Bulk Cache URLs")
with st.sidebar.form(key="bulk_cache_form"):
    bulk_urls = st.text_area("Bulk URLs (one per line)", "")
    submit_bulk = st.form_submit_button("Bulk Cache URLs")
    if submit_bulk and bulk_urls:
        url_list = [u.strip() for u in bulk_urls.splitlines() if u.strip()]
        bulk_errors = []
        for url in url_list:
            errors = trigger_both_variants(url)
            if errors:
                bulk_errors.append(f"{url}: {', '.join(errors)}")
        if not bulk_errors:
            st.sidebar.success("All URLs submitted for caching (desktop & mobile).")
        else:
            st.sidebar.error("Some URLs failed to cache:\n" + "\n".join(bulk_errors))

# --- Cache from Sitemap ---
st.sidebar.markdown("---")
st.sidebar.subheader("Cache URLs from Sitemap.xml")
with st.sidebar.form(key="sitemap_cache_form"):
    sitemap_url = st.text_input("Sitemap URL", "")
    submit_sitemap = st.form_submit_button("Cache Sitemap URLs")
    if submit_sitemap and sitemap_url:
        try:
            resp = requests.get(sitemap_url)
            urls = re.findall(r'<loc>(.*?)</loc>', resp.text)
            sitemap_errors = []
            # Fetch current cache to avoid recaching already-cached URLs
            current_cache = fetch_cache()  # returns {url: [variants]}
            for url in urls:
                if url in current_cache:
                    continue  # Skip already cached URLs
                errors = trigger_both_variants(url)
                if errors:
                    sitemap_errors.append(f"{url}: {', '.join(errors)}")
            if not sitemap_errors:
                st.sidebar.success("All uncached sitemap URLs submitted for caching (desktop & mobile).")
            else:
                st.sidebar.error("Some sitemap URLs failed to cache:\n" + "\n".join(sitemap_errors))
        except Exception as e:
            st.sidebar.error(f"Error fetching sitemap: {e}")

# --- Clear All Cache ---
st.sidebar.markdown("---")
if st.sidebar.button("Clear All Cache", type="primary"):
    try:
        # Fetch all cache items
        resp = requests.get(API_BASE)
        data = resp.json()
        urls = [item.get("url", "") for item in data.get("items", [])]
        errors = []
        for url in urls:
            del_resp = requests.delete(API_BASE, params={"url": url})
            try:
                del_data = del_resp.json()
            except Exception:
                errors.append(f"Non-JSON response for {url}: {del_resp.text}")
                continue
            if not del_data.get("success"):
                errors.append(f"Failed to delete cache for {url}: {del_data.get('error', 'Unknown error')}")
        if not errors:
            st.success("All cache entries cleared.")
            st.rerun()
        else:
            st.error("Some caches could not be cleared:\n" + "\n".join(errors))
    except Exception as e:
        st.error("Error clearing cache: {}".format(e))

def fetch_cache():
    try:
        resp = requests.get(API_BASE)
        data = resp.json()
        if data.get("success"):
            items = data.get("items", [])
            # Group by URL, show variants in dropdown
            url_dict = {}
            for item in items:
                url = item.get("url", "")
                variant = item.get("variant", "desktop")
                if url not in url_dict:
                    url_dict[url] = []
                url_dict[url].append(item)
            return url_dict
        else:
            st.error("Failed to fetch cache: {}".format(data.get("error", "Unknown error")))
            return {}
    except Exception as e:
        st.error("Error fetching cache: {}".format(e))
        return {}

def format_datetime(dt):
    try:
        return datetime.fromisoformat(dt).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt

# --- Main Table ---
cache_dict = fetch_cache()
st.subheader(f"Cached URLs ({len(cache_dict)})")

# Bulk variant filter
variant_filter = st.selectbox("Show variant", options=["all", "desktop", "mobile"], index=0)

# Filter/search
search_term = st.text_input("Search cached URLs", "")
filtered_urls = [url for url in cache_dict if search_term.lower() in url.lower()]

if not filtered_urls:
    st.info("No cached items found.")
else:
    for idx, url in enumerate(filtered_urls):
        variants = cache_dict[url]
        # Apply bulk variant filter
        if variant_filter != "all":
            variants = [item for item in variants if item.get("variant", "desktop") == variant_filter]
        if not variants:
            continue
        for v_idx, item in enumerate(variants):
            with st.expander(f"{url} [{item.get('variant','desktop')}]", expanded=False):
                st.write(f"**Variant:** {item.get('variant','desktop')}")
                st.write(f"**Status:** {item.get('statusCode', '')}")
                st.write(f"**Cached At:** {format_datetime(item.get('cachedAt', ''))}")
                st.write(f"**Expires At:** {format_datetime(item.get('expiresAt', ''))}")
                cols = st.columns(2)
                if cols[0].button("Delete", key=f"delete_{idx}_{v_idx}_{item.get('variant','desktop')}"):
                    try:
                        del_resp = requests.delete(API_BASE, params={"url": url})
                        try:
                            del_data = del_resp.json()
                        except Exception:
                            st.error(f"Non-JSON response for {url}: {del_resp.text}")
                            continue
                        if not del_data.get("success"):
                            st.error(f"Failed to delete cache: {del_data.get('error', 'Unknown error')}")
                            continue
                        st.success("Cache deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error("Error deleting cache: {}".format(e))
                if cols[1].button("Refresh", key=f"refresh_{idx}_{v_idx}_{item.get('variant','desktop')}"):
                    try:
                        del_resp = requests.delete(API_BASE, params={"url": url})
                        try:
                            del_data = del_resp.json()
                        except Exception:
                            st.error(f"Non-JSON response from API (delete): {del_resp.text}")
                            continue
                        if not del_data.get("success"):
                            st.error("Failed to delete cache before refresh: {}".format(del_data.get("error", "Unknown error")))
                            continue
                        trigger_both_variants(url)
                        st.success("Cache refresh initiated.")
                        st.rerun()
                    except Exception as e:
                        st.error("Error refreshing cache: {}".format(e))

st.caption("Prerender Cache Manager - Streamlit UI")
