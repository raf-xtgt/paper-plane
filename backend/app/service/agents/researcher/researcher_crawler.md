## Web Crawler
This is a dynamic web crawler to extract information from non-static websites.

### Core Requirements
- The crawler must use headless browsing to navigate through the website.
- Given a website url, visit the site, execute JavaScript, render the full DOM.
- It will then extract the content of the page as markdown. 

### Crawl Strategy
- The crawler will scan through the entire page that is the website_url.
- It will then extract the information on the page as a markdown.
- The crawler must maintain a list of visited urls to prevent duplicate crawling.
- The crawler will repeat the process for each page found in the base page.
- The crawler will stop when it has crawled through all the pages.
- The crawler will output a json file with the list of contacts found in the website.
- The final output schema will follow this example:
```
{
    "page_url": "https://example.com",
    "markdown_content":""
}
```

### Libraries:
- playwright

### Constraints:
- The crawler must be able to handle dynamic content.
- The crawler must be able to handle pagination.
- The crawler must be able to handle infinite scroll.
- The crawler must be able to handle lazy loading.
- The crawler must not use the beautifulsoup libraries.