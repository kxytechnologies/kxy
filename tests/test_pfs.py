import numpy as np

import kxy
from kxy.learning import get_sklearn_learner, get_lightgbm_learner_learning_api, get_xgboost_learner
from kxy.pfs import PFSPredictor, PFS, PCA
from kxy_datasets.regressions import Abalone
from kxy_datasets.classifications import BankNote, BankMarketing


def test_shape():
	dataset = Abalone()
	target_column = dataset.y_column
	df = dataset.df

	# Features generation
	features_df = df.kxy.generate_features(entity=None, max_lag=None, entity_name='*', exclude=[target_column])
	y = features_df[target_column].values
	x_columns = [_ for _ in features_df.columns if _ != target_column]
	x = features_df[x_columns].values

	# Principal features construction
	feature_directions = PFS().fit(x, y)
	assert feature_directions.shape[1] == x.shape[1]

	predictor = PFSPredictor()
	learner_func = get_sklearn_learner('sklearn.ensemble.RandomForestRegressor', random_state=0)
	results = predictor.fit(features_df, target_column, learner_func)
	feature_directions = results['Feature Directions']
	assert feature_directions.shape[1] == x.shape[1]


def test_norm():
	dataset = Abalone()
	target_column = dataset.y_column
	df = dataset.df

	# Features generation
	features_df = df.kxy.generate_features(entity=None, max_lag=None, entity_name='*', exclude=[target_column])
	y = features_df[target_column].values
	x_columns = [_ for _ in features_df.columns if _ != target_column]
	x = features_df[x_columns].values

	# Principal features construction
	feature_directions = PFS().fit(x, y)
	n_directions = feature_directions.shape[0]
	for i in range(n_directions):
		assert np.allclose(np.dot(feature_directions[i, :], feature_directions[i, :]), 1.)

	predictor = PFSPredictor()
	learner_func = get_sklearn_learner('sklearn.ensemble.RandomForestRegressor', random_state=0)
	results = predictor.fit(features_df, target_column, learner_func)
	feature_directions = results['Feature Directions']
	n_directions = feature_directions.shape[0]
	for i in range(n_directions):
		assert np.allclose(np.dot(feature_directions[i, :], feature_directions[i, :]), 1.)


def test_pfs_feature_selection():
	# Regression
	xgboost_regressor_cls = get_xgboost_learner('xgboost.XGBRegressor')
	dataset = Abalone()
	target_column = dataset.y_column
	df = dataset.df

	# Features generation
	features_df = df.kxy.generate_features(entity=None, max_lag=None, entity_name='*', exclude=[target_column])

	# Model building
	results = features_df.kxy.fit(target_column, xgboost_regressor_cls, \
		problem_type='regression', feature_selection_method='pfs')
	assert results['Feature Directions'].shape[1] == features_df.shape[1]-1
	predictor = results['predictor']
	predictions = predictor.predict(features_df)
	assert len(predictions.columns) == 1
	assert target_column in predictions.columns
	assert set(features_df.index).difference(set(predictions.index)) == set()
	assert set(predictions.index).difference(set(features_df.index)) == set()


def test_save_pfs():
	# Regression
	xgboost_regressor_cls = get_xgboost_learner('xgboost.XGBRegressor')
	dataset = Abalone()
	target_column = dataset.y_column
	df = dataset.df

	# Features generation
	features_df = df.kxy.generate_features(entity=None, max_lag=None, entity_name='*', exclude=[target_column])

	# Model building
	path = 'Abalone'
	results = features_df.kxy.fit(target_column, xgboost_regressor_cls, \
		problem_type='regression', feature_selection_method='pfs', \
		path=path)
	loaded_predictor = PFSPredictor().load(path, xgboost_regressor_cls)
	feature_directions = loaded_predictor.feature_directions
	assert feature_directions.shape[1] == features_df.shape[1]-1
	predictions = loaded_predictor.predict(features_df)
	assert len(predictions.columns) == 1
	assert target_column in predictions.columns
	assert set(features_df.index).difference(set(predictions.index)) == set()
	assert set(predictions.index).difference(set(features_df.index)) == set()


def test_pfs_accuracy():
	# Generate the data
	seed = 1
	np.random.seed(seed)
	d = 100
	w = np.ones(d)/d
	x = np.random.randn(10000, d)
	xTw = np.dot(x, w)
	y = xTw + 2.*xTw**2 + 0.5*xTw**3

	# Run PFS
	from kxy.misc.tf import set_default_parameter
	set_default_parameter('lr', 0.001)
	selector = PFS()
	selector.fit(x, y, epochs=21, seed=seed, expand_y=True)

	# Learned principal directions
	F = selector.feature_directions

	# Learned principal features
	z = np.dot(x, F.T)

	# Accuracy
	true_f_1 = w/np.linalg.norm(w)
	learned_f_1 = F[0, :]
	e = np.linalg.norm(true_f_1-learned_f_1)

	assert e <= 0.10
	assert selector.mutual_information > 1.0


def test_feature_extraction():
	# Generate the data
	seed = 1
	np.random.seed(seed)
	d = 100
	w = np.ones(d)/d
	x_train = np.random.randn(10000, d)
	x_trainTw = np.dot(x_train, w)
	y_train = x_trainTw + 2.*x_trainTw**2 + 0.5*x_trainTw**3

	# Run PFS
	from kxy.misc.tf import set_default_parameter
	set_default_parameter('lr', 0.001)
	selector = PFS()
	selector.fit(x_train, y_train, epochs=21, seed=seed, expand_y=False)

	# Extract the features
	fx_train = selector.max_ent_features_x(x_train)
	assert fx_train.shape[0] == x_train.shape[0]

	# Run a linear regression relating learned features to y
	from sklearn.linear_model import LinearRegression
	from sklearn.metrics import r2_score

	# Training
	m = LinearRegression()
	m.fit(fx_train, y_train)

	# Testing accuracy
	x_test = np.random.randn(10000, d)
	x_testTw = np.dot(x_test, w)
	y_test = x_testTw + 2.*x_testTw**2 + 0.5*x_testTw**3

	fx_test = selector.max_ent_features_x(x_test)
	assert fx_test.shape[0] == x_test.shape[0]

	y_test_predicted = m.predict(fx_test)
	testing_r2 = r2_score(y_test_predicted, y_test)

	y_train_predicted = m.predict(fx_train)
	training_r2 = r2_score(y_train_predicted, y_train)

	assert training_r2>0.99, 'Learned features should be good for linear regression in-sample'
	assert testing_r2>0.99, 'Learned features should be good for linear regression out-of-sample'


