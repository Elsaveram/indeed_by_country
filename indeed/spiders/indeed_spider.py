# -*- coding: utf-8 -*-
from scrapy import Spider, Request
import re
import urllib
from indeed.items import IndeedJobItem

class IndeedSpider(Spider):
    name = 'indeed_spider'
    allowed_domains = ['indeed.com']
    base_url = r'https://www.indeed.com/jobs?'
    base_query_params = { 'q':'data scientist', 'jt':'fulltime' , 'l':'New York, NY', 'fromage':'30' }

    # Filters used are full time jobs opened in the last 30 days within 25 miles (default)
    start_urls = [base_url + urllib.parse.urlencode(base_query_params)]


    def parse(self, response):
        # Find the total number of pages in the result so that we can decide how many urls to scrape next
        text = response.xpath('//div[@id="searchCount"]/text()').extract_first().replace(",","")
        current_page, total_jobs = map(lambda x: int(x), re.findall('\d+', text))

        print(total_jobs)
        # List comprehension to construct all the urls
        all_result_pages = [ self.start_urls[0] + '&start=' + str(start_job) for start_job in range(0,total_jobs,10)]

        # Yield the requests to different search result urls,
        # using parse_result_page function to parse the response.
        for url in all_result_pages[:2]:
            yield Request(url=url, callback=self.parse_result_page)

    def parse_result_page(self, response):
        # Parse the jobs in each page
        jobs_on_page = response.xpath("//td[@id='resultsCol']").xpath("./div[@data-tn-component='organicJob']")

        for job in jobs_on_page:
            # Initiating an empty dictionary to collect the meta information to "piggy-back" forward
            job_to_save = {}

            # Location. It includes the city and some times the state and zip code
            location = job.xpath("./span[@class='location']/text()").extract_first().split(",")
            job_to_save['city'] = location[0].strip()
            job_to_save['region'] = ''.join(re.findall('[a-zA-Z]+', location[1]))
            job_to_save['region_code'] = ''.join(re.findall('\d+', location[1]))

            # Company rating. The rating in the attribute "style" of the class "span" is shown as the number of pixels.
            # The total number of pixels that corresponds to a 5 star review can be found in the parent "span" class
            # and it is equal to 60 pixels.
            rating_style = job.xpath(".//span/@style").extract_first()
            try:
                job_to_save['rating'] = float(''.join(re.findall('\d+.\d+', rating_style))) * 5 / 60
            except:
                job_to_save['rating'] = ""

            # Title, company, how long ago the position was open.
            job_to_save['indeed_id'] = job.xpath("./@data-jk").extract_first()
            job_to_save['title'] = job.xpath("./h2/a/@title").extract_first()
            job_to_save['company'] = ''.join(job.xpath(".//span[@class='company']//text()").extract()).strip()
            job_to_save['how_long_open'] = job.xpath(".//span[@class='date']/text()").extract_first()

            # Number of company reviews can be empty so it's wraped it in a try block
            try:
                reviews = job.xpath(".//span[@class='slNoUnderline']/text()").extract_first()
                job_to_save['number_of_reviews'] = int(''.join(re.findall('\d+', reviews)))
            except:
                job_to_save['number_of_reviews'] = ""

            # The job details link is a relative link. Concatenate with start url
            link_to_job_detail = "https://www.indeed.com" + job.xpath("./h2/a/@href").extract_first()

            # Pass the meta information to the job detail page where the summary is going to be extracted
            yield Request(url=link_to_job_detail, meta=job_to_save, callback=self.parse_job_detail_page)


    def parse_job_detail_page(self, response):
        job_to_save = IndeedJobItem()
        indeed_keys = vars(IndeedJobItem)['fields'].keys()
        meta_keys = response.meta.keys()

        # In order to remove unwanted columns from the meta object, we create a dictonary by using the intersecton of
        # the indeed class keys and the meta keys
        job_to_save = dict((k, response.meta[k]) for k in indeed_keys & meta_keys )

        # Add a striped version of the summary
        summary_raw = ''.join(response.xpath("//span[@class='summary']//text()").extract())
        job_to_save['summary'] = summary_raw.replace('\n','')

        # Uncomment if summary is not working.
        # print("="*50)
        # print(summary_raw.replace('\n',''))
        # print(job_to_save)

        yield job_to_save
