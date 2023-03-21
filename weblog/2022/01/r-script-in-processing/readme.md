---
Date: 2022-01-16 03:50
Tags: Cloud, AWS
Stub: r-script-in-processing
---

# Run a simple R script using SageMaker Processing

Starting with a basic example provided by AWS, I've made a few minor changes.

![img1](https://cdn.some.pics/mihobu/6419d4ecd90b1.png)

When I’m learning new things, I almost always take a very deliberate (read: slow) cumulative approach. I start with simple, even trivial, examples and build my understanding one concept at a time. It's just how my brain works.
I’ve been exploring [SageMaker Processing](https://mb.monkeywalk.com/2022/01/what-is-amazon-sagemaker-processing) lately, specifically the ability to run R scripts as part of a data science workflow. AWS provides a lot of excellent examples in their massive [Amazon SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples) GitHub repo, so that’s where I started.

The “[Using R in SageMaker Processing](https://github.com/aws/amazon-sagemaker-examples/blob/master/r_examples/r_in_sagemaker_processing/r_in_sagemaker_processing.ipynb)” example notebook shows how to build a Docker container with R and then create and run a Processing job using that container. It loads a small dataset and (using the Tidyverse packages) performs some data aggregation and generates a bar chart. The bar chart and a copy of the aggregated data are then stored on S3.

## (Non-)Sensible Defaults?

One thing that bugs me about a lot of AWS examples is that they rely heavily on the default behavior of the various API calls involved—and anyone who has read the API docs knows that the default behaviors are not always well documented. In particular, many (and I mean MANY) API calls make choices about how various resources are named. In the case of SageMaker Processing, a new copy of the code is placed in a uniquely-named S3 object every time the script runs—unless you configure specific locations.

So, to keep myself sane and to prevent having dozens of folders in S3 with duplicate copies of my script, I made a few modifications to the basic example.

You can find [my modified copy on GitHub](https://github.com/mihobu/sagemaker-processing-examples/blob/main/basic-r-example/r_in_sagemaker_processing.ipynb).

![img2](https://cdn.some.pics/mihobu/6419d50b477ac.png)

## Stay tuned

Next on my list is to run an R script in SageMaker Processing using a customized R container that does not have 15 medium and 36 other vulnerabilities, as the off-the-shelf example does. I’ve already done something very similar to [enable R code using Lambda](https://github.com/mihobu/r-lambda-runtime), so I hope that it won’t be too difficult to get working. Stay tuned.
