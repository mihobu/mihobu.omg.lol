---
Date: 2022-01-09 03:54
Tags: Cloud, AWS
---

# What is Amazon SageMaker Processing?

When AWS [announced](https://aws.amazon.com/blogs/aws/amazon-sagemaker-processing-fully-managed-data-processing-and-model-evaluation/) Amazon SageMaker Processing back in 2019, I was fairly busy working out how to get [SageMaker](https://aws.amazon.com/sagemaker/) Tuning, Training, and Batch Inference jobs and [AWS Glue](https://aws.amazon.com/glue/) pre- and postprocessing jobs orchestrated to run at scale using an S3 data lake. I remember seeing the new item in the SageMaker service menu appear one day and thinking, “What the heck is Processing? Ugh, I’ll look at it later.”

Now I wish I hadn’t kicked the can down the road. I’ve recently begun to learn about Processing and I think it’ll solve some important problems as I begin migrating some analytics workloads to the cloud. It seems like a good time to share what I’m learning as I go.

If you haven't read about it already, the [introduction](https://docs.aws.amazon.com/sagemaker/latest/dg/processing-job.html) in the Developer Guide is worth a look. It says, in part:

> With Processing, you can use a simplified, managed experience on SageMaker to run your data processing workloads, such as feature engineering, data validation, model evaluation, and model interpretation. You can also use the Amazon SageMaker Processing APIs during the experimentation phase and after the code is deployed in production to evaluate performance.

## So what is Amazon SageMaker Processing really?

That sounds like a lot of marketing malarkey to me. I’d describe Processing like this: it’s sort of like [AWS Glue](https://aws.amazon.com/glue/), but different/better. Some key features are that you can

- Run Spark scripts using either Python (PySpark) or Java
- Run python scripts using the Scikit-Learn API
- Read and write data to and from S3
- Run at scale (you choose the type and number of instances)
- Bring your own containerized scripts
- Run jobs interactively (e.g. from a SageMaker notebook)
- Trigger or schedule jobs using EventBridge Rules

The SageMaker SDK provides several processors for launching Processing jobs:

- [PySparkProcessor](https://sagemaker.readthedocs.io/en/stable/amazon_sagemaker_processing.html#pysparkprocessor) for Spark scripts written in Python.
- [SparkJarProcessor](https://sagemaker.readthedocs.io/en/stable/amazon_sagemaker_processing.html#sparkjarprocessor) for Spark scripts written in Java/Scala.
- [SKLearnProcessor](https://sagemaker.readthedocs.io/en/stable/frameworks/sklearn/sagemaker.sklearn.html?highlight=sklearnprocessor#sagemaker.sklearn.processing.SKLearnProcessor) for Python scripts using the first-party Scikit-Learn contatiner.
- [ScriptProcessor](https://sagemaker.readthedocs.io/en/stable/api/training/processing.html#sagemaker.processing.ScriptProcessor) for scripts that use a container of your own.
- [FrameworkProcessor](https://sagemaker.readthedocs.io/en/stable/api/training/processing.html#sagemaker.processing.FrameworkProcessor) allows you to use any of the existing built-in framework processors (MXNet, HuggingFace, PyTorch, Scikit-Learn, etc.) with custom dependencies.

## Some Introductory Examples

If you haven't use Processing before, I recommend the following examples provided as part of the huge [Amazon SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples) GitHub repo:

- This [introductory example](https://github.com/aws/amazon-sagemaker-examples/blob/master/sagemaker_processing/spark_distributed_data_processing/sagemaker-spark-processing.ipynb) is a good place to start, with PySpark and Java/Scala examples.
- [Scikit-Learn Data Processing and Model Evaluation](https://github.com/aws/amazon-sagemaker-examples/blob/master/sagemaker_processing/scikit_learn_data_processing_and_model_evaluation/scikit_learn_data_processing_and_model_evaluation.ipynb) takes you through data preprocessing, training, and model evaluation using the SKLearnProcessor. There’s also a short section on customization using the ScriptProcessor.

## More to come…

I’m especially excited about the ScriptProcessor because I’m interested in scheduling [R](https://www.r-project.org/) scripts in the cloud. I’ll continue to share what I learn in future articles.