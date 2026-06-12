```yaml
prompt_name: "kaggle_50_startups_crisp_dm_sklearn_v2"
version: "v2"
language: "English"
task_type: "machine_learning_regression_project"

objective: >
  Write a complete Python sklearn program to solve the Kaggle 50 Startups
  regression problem by following the CRISP-DM methodology. The program should
  predict startup Profit using business spending features and location data.
  The solution must also include feature experiments based on expert discussion
  from R&D, Marketing, Sales, Finance, Regional Policy, and Data Science perspectives.

dataset:
  name: "Kaggle 50 Startups"
  url: "https://github.com/harimittapalli/Mulitple-Linear-Reggression/raw/master/50_Startups.csv"
  target_column: "Profit"
  feature_columns:
    - "R&D Spend"
    - "Administration"
    - "Marketing Spend"
    - "State"

problem_type:
  machine_learning_type: "Supervised Learning"
  task: "Regression"
  main_algorithm: "Multiple Linear Regression"
  library: "scikit-learn"

expert_discussion_summary:
  context: >
    Assume experts from different domains, including R&D, Marketing, Sales,
    Finance, State or Regional Policy, and Data Science, discussed this problem
    for five rounds. Their final conclusion should be used to guide feature
    interpretation and experiment design.
  final_consensus: >
    Profit in the 50 Startups dataset is mainly driven by how a company allocates
    its resources, not only by its location. R&D Spend is the core profit driver
    because it represents product development, innovation, and technical
    capability. Marketing Spend is an important supporting feature because it can
    amplify product value and increase market exposure. Administration is less
    certain because it represents operating cost rather than direct profit
    generation. State may reflect regional differences, but due to the small
    dataset size, it should be treated as a supporting feature and should not be
    over-interpreted.
  feature_priority:
    - rank: 1
      feature: "R&D Spend"
      importance: "Very High"
      recommendation: "Strongly keep"
      reason: >
        It directly reflects innovation, product development, and technical
        capability, which are fundamental drivers of startup profitability.
    - rank: 2
      feature: "Marketing Spend"
      importance: "Medium to High"
      recommendation: "Keep and test"
      reason: >
        It may increase brand awareness, market exposure, and sales opportunities,
        but its effect may depend on product quality and R&D strength.
    - rank: 3
      feature: "Administration"
      importance: "Uncertain"
      recommendation: "Test carefully"
      reason: >
        It represents operating and management costs, which may not directly
        generate profit. It may be useful, weak, or noisy.
    - rank: 4
      feature: "State"
      importance: "Supporting"
      recommendation: "Encode and test, but do not over-interpret"
      reason: >
        It may reflect regional differences such as market environment, labor
        cost, tax policy, and business resources. However, because the dataset
        has only 50 rows, its effect should be interpreted carefully.

crisp_dm_steps:
  step_1_business_understanding:
    goal: >
      Understand how startup spending affects company profit and build a model
      that can predict Profit.
    business_questions:
      - "Which feature has the strongest influence on startup profit?"
      - "Is R&D Spend the most important predictor of Profit?"
      - "Does Marketing Spend improve prediction performance?"
      - "Does Administration help the model, or does it add noise?"
      - "Does State provide useful regional information?"
      - "Can we build a reliable regression model to estimate startup Profit?"
    expert_business_logic: >
      From the expert discussion, R&D Spend should be treated as the core
      business driver. Marketing Spend should be treated as a value amplifier.
      Administration should be treated as a possible operating-cost feature.
      State should be treated as a supporting regional feature.
    expected_business_value: >
      Help startup founders, investors, financial analysts, and business managers
      understand how resource allocation affects profitability and improve
      budgeting decisions.

  step_2_data_understanding:
    required_checks:
      - "Show first 5 rows using df.head()"
      - "Show dataset shape"
      - "Show dataset information using df.info()"
      - "Show basic statistics using df.describe()"
      - "Check missing values"
      - "Check duplicate rows"
      - "Show State value counts"
      - "Optionally show correlation matrix for numerical features"
    feature_understanding:
      rd_spend: >
        R&D Spend is expected to be the strongest predictor because it directly
        represents innovation, product development, and technical investment.
      marketing_spend: >
        Marketing Spend may help increase brand awareness, customer reach, and
        sales. It should be tested because it may also overlap with company size
        or R&D investment.
      administration: >
        Administration represents operating and management costs. It may be
        weaker or noisy because it does not directly generate profit.
      state: >
        State is a categorical feature. It may represent regional differences,
        but because the dataset is small, it should be treated as a supporting
        feature rather than a main predictor.
      profit: >
        Profit is the continuous numerical target variable. Since it is numerical,
        the problem is a regression task.

  step_3_data_preparation:
    requirements:
      - "Load dataset from the given URL"
      - "Separate X features and y target"
      - "Use train_test_split with test_size=0.2 and random_state=42"
      - "Use OneHotEncoder for State"
      - "Use OneHotEncoder(drop='first') to avoid dummy variable trap"
      - "Use ColumnTransformer for preprocessing"
      - "Use Pipeline to combine preprocessing and LinearRegression"
    preprocessing_notes:
      numerical_features:
        - "R&D Spend"
        - "Administration"
        - "Marketing Spend"
      categorical_features:
        - "State"
      target:
        - "Profit"
      warning: >
        Since the dataset has only 50 rows, avoid adding unnecessary complexity.
        Each added feature should be justified by both model metrics and business
        logic.

  step_4_modeling:
    model: "LinearRegression"
    modeling_strategy: >
      Do not build only one all-feature model. Instead, run feature experiments
      to test whether each feature group provides additional predictive value.
    experiment_design:
      - model_name: "Model A: R&D Spend Only"
        features:
          - "R&D Spend"
        categorical_features: []
        purpose: >
          Test the strongest single feature and establish whether R&D alone
          explains most of Profit.
      - model_name: "Model B: R&D Spend + Marketing Spend"
        features:
          - "R&D Spend"
          - "Marketing Spend"
        categorical_features: []
        purpose: >
          Test whether Marketing Spend adds value beyond R&D Spend.
      - model_name: "Model C: R&D Spend + Marketing Spend + Administration"
        features:
          - "R&D Spend"
          - "Marketing Spend"
          - "Administration"
        categorical_features: []
        purpose: >
          Test whether Administration improves prediction or adds noise.
      - model_name: "Model D: All Features Including State"
        features:
          - "R&D Spend"
          - "Marketing Spend"
          - "Administration"
          - "State"
        categorical_features:
          - "State"
        purpose: >
          Test whether State improves performance after One-Hot Encoding.
      - model_name: "Model E: State Only"
        features:
          - "State"
        categorical_features:
          - "State"
        purpose: >
          Test whether location alone can predict Profit.
    required_model_outputs:
      - "Train each experiment using sklearn Pipeline"
      - "Save each trained model in a dictionary"
      - "Collect all evaluation results into a pandas DataFrame"
      - "Sort model results by Adjusted R2 descending and RMSE ascending"

  step_5_evaluation:
    metrics:
      - "R2 Score"
      - "Adjusted R2"
      - "MAE"
      - "MSE"
      - "RMSE"
    evaluation_rules:
      - "Do not only use R2 because R2 can increase when more features are added"
      - "Use Adjusted R2 to consider the number of predictors"
      - "Use RMSE and MAE to compare prediction error"
      - "Use coefficient interpretation to understand feature direction and impact"
      - "Use expert business logic to decide whether a feature makes sense"
    best_model_criteria:
      - "Higher Adjusted R2"
      - "Lower RMSE"
      - "Lower MAE"
      - "Reasonable feature coefficients"
      - "Strong business interpretation"
      - "Avoid unnecessary noisy features"
    state_interpretation_rule: >
      If adding State does not clearly improve Adjusted R2 or reduce RMSE, treat
      State as a weak supporting feature. If State-only performs poorly, conclude
      that location alone is not enough to explain Profit.

  step_6_deployment_conclusion:
    required_outputs:
      - "Model comparison table"
      - "Best model name"
      - "Best model coefficients"
      - "Feature ranking based on coefficients and business logic"
      - "Business interpretation"
      - "Final conclusion"
    expected_conclusion: >
      R&D Spend is expected to be the most important predictor of Profit.
      Marketing Spend may provide additional value as a market exposure and sales
      support feature. Administration may be weaker or unstable because it
      represents operating cost. State can be tested as a supporting feature, but
      it should not be over-interpreted because the dataset only has 50 rows.
      The final model should be selected based on Adjusted R2, RMSE, MAE,
      coefficient interpretation, and business logic.

code_requirements:
  structure:
    - "Step 0: Import libraries"
    - "Step 1: Business Understanding comment block"
    - "Step 2: Data Understanding"
    - "Step 3: Data Preparation"
    - "Helper function: adjusted_r2_score"
    - "Helper function: run_experiment"
    - "Step 4: Modeling"
    - "Step 5: Evaluation"
    - "Helper function: get_model_coefficients"
    - "Step 6: Expert-Based Business Conclusion"
  coding_style:
    - "Use clear section headers"
    - "Use comments to explain CRISP-DM steps"
    - "Use reusable functions"
    - "Print readable outputs"
    - "Keep the code beginner-friendly"
    - "Make the script executable from start to finish"
  libraries:
    - "pandas"
    - "numpy"
    - "sklearn.model_selection.train_test_split"
    - "sklearn.linear_model.LinearRegression"
    - "sklearn.compose.ColumnTransformer"
    - "sklearn.preprocessing.OneHotEncoder"
    - "sklearn.pipeline.Pipeline"
    - "sklearn.metrics.r2_score"
    - "sklearn.metrics.mean_absolute_error"
    - "sklearn.metrics.mean_squared_error"

final_instruction: >
  Generate a complete Python script named 50_startups_crisp_dm_v2.py.
  The script must be executable from start to finish. It should load the data,
  perform CRISP-DM-based analysis, run all five feature experiments, compare
  model results, select the best model, show coefficients, and print a final
  expert-based business conclusion. The conclusion must reflect the five-round
  expert discussion: R&D Spend is the core predictor, Marketing Spend is an
  important amplifier, Administration is uncertain and should be tested, and
  State is only a supporting feature that should not be over-interpreted.
```
