Grad Cafe Analytics
===================

A test-driven, documented data and web analysis service for
`thegradcafe.com <https://www.thegradcafe.com>`_ admissions data.

The service has two halves:

* a **Web** layer (Flask) that serves an Analysis page with *Pull Data* and
  *Update Analysis* buttons, and
* a **Data** layer (ETL + PostgreSQL) that scrapes, cleans, loads, and
  summarises applicant entries.

This documentation covers how to set the project up, how the pieces fit
together, the API reference for every module, and how to run the test suite.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   overview
   architecture
   api
   testing
   operations
