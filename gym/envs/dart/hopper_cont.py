__author__ = 'yuwenhao'

import numpy as np
from gym import utils, spaces
from gym.envs.dart import dart_env

from keras.models import Sequential, load_model
from keras.layers.core import Dense, Dropout, Activation
from keras.layers.core import Layer
import theano.tensor as T, theano
from keras import backend as K
import numpy as np
import copy
import os

import joblib

from gym.envs.dart.parameter_managers import *

# WARNING: A lot of hand-coded stuff for now
class DartHopperEnvCont(dart_env.DartEnv, utils.EzPickle):
    def __init__(self):
        self.control_bounds = np.array([[1.0, 1.0, 1.0],[-1.0, -1.0, -1.0]])
        self.action_scale = 200
        self.train_UP = True
        self.noisy_input = False
        self.resample_MP = True  # whether to resample the model paraeters
        obs_dim = 11

        self.param_manager = hopperContactMassManager(self)
        if self.train_UP:
            obs_dim += self.param_manager.param_dim

        modelpath = os.path.join(os.path.dirname(__file__), "models")
        self.UPs = [joblib.load(os.path.join(modelpath, 'UP_torso1.pkl')), joblib.load(os.path.join(modelpath, 'UP_torso0.pkl'))]
        self.UP_mpid = [[0], [0]]

        dart_env.DartEnv.__init__(self, 'hopper_capsule.skel', 4, obs_dim, self.control_bounds)

        self.act_dim = 2
        self.action_space = spaces.Discrete(2)

        self.dart_world.set_collision_detector(3)  # 3 is ode collision detector

        utils.EzPickle.__init__(self)

    def _step(self, action):
        pre_state = [self.state_vector()]
        if self.train_UP:
            pre_state.append(self.param_manager.get_simulator_parameters())

        state = np.concatenate([
            self.robot_skeleton.q[1:],
            np.clip(self.robot_skeleton.dq, -10, 10)
        ])
        state[0] = self.robot_skeleton.bodynodes[2].com()[1]
        up_input = np.concatenate([state, self.param_manager.get_simulator_parameters()[self.UP_mpid[action]]])
        act, actinfo = self.UPs[action].get_action(up_input)
        a = actinfo['mean']

        clamped_control = np.array(a)
        for i in range(len(clamped_control)):
            if clamped_control[i] > self.control_bounds[0][i]:
                clamped_control[i] = self.control_bounds[0][i]
            if clamped_control[i] < self.control_bounds[1][i]:
                clamped_control[i] = self.control_bounds[1][i]
        tau = np.zeros(self.robot_skeleton.ndofs)
        tau[3:] = clamped_control * self.action_scale
        posbefore = self.robot_skeleton.q[0]
        self.do_simulation(tau, self.frame_skip)
        posafter, ang = self.robot_skeleton.q[0, 2]
        height = self.robot_skeleton.bodynodes[2].com()[1]

        contacts = self.dart_world.collision_result.contacts
        total_force_mag = 0
        for contact in contacts:
            total_force_mag += np.square(contact.force).sum()

        joint_limit_penalty = 0
        for j in [-2]:
            if (self.robot_skeleton.q_lower[j] - self.robot_skeleton.q[j]) > -0.05:
                joint_limit_penalty += abs(1.5)
            if (self.robot_skeleton.q_upper[j] - self.robot_skeleton.q[j]) < 0.05:
                joint_limit_penalty += abs(1.5)

        alive_bonus = 1.0
        reward = 0.6 * (posafter - posbefore) / self.dt
        reward += alive_bonus
        reward -= 1e-3 * np.square(a).sum()
        reward -= 5e-1 * joint_limit_penalty
        # reward -= 1e-7 * total_force_mag

        s = self.state_vector()
        done = not (np.isfinite(s).all() and (np.abs(s[2:]) < 100).all() and
                    (height > .7) and (height < 1.8) and (abs(ang) < .4))
        ob = self._get_obs()

        return ob, reward, done, {'model_parameters': self.param_manager.get_simulator_parameters(),
                                  'vel_rew': (posafter - posbefore) / self.dt, 'action_rew': 1e-3 * np.square(a).sum(),
                                  'forcemag': 1e-7 * total_force_mag, 'done_return': done}

    def _get_obs(self):
        state =  np.concatenate([
            self.robot_skeleton.q[1:],
            np.clip(self.robot_skeleton.dq,-10,10)
        ])
        state[0] = self.robot_skeleton.bodynodes[2].com()[1]

        if self.train_UP:
            state = np.concatenate([state, self.param_manager.get_simulator_parameters()])
        if self.noisy_input:
            state = state + np.random.normal(0, .01, len(state))
        return state

    def reset_model(self):
        self.dart_world.reset()
        qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.005, high=.005, size=self.robot_skeleton.ndofs)
        self.set_state(qpos, qvel)
        if self.resample_MP:
            self.param_manager.resample_parameters()
        self.state_action_buffer = [] # for UPOSI

        state = self._get_obs()

        return state

    def viewer_setup(self):
        self._get_viewer().scene.tb.trans[2] = -5.5