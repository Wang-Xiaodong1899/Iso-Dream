# Copyright 2017 The dm_control Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or  implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================

"""Reacher domain."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections

from dm_control import mujoco
from dm_control.rl import control
from dm_control.suite import base
from dm_control.suite import common
from dm_control.suite.utils import randomizers
from dm_control.utils import containers
from dm_control.utils import rewards
import numpy as np

SUITE = containers.TaggedTasks()
_DEFAULT_TIME_LIMIT = 20
_BIG_TARGET = .05
_SMALL_TARGET = .015


def get_model_and_assets():
  """Returns a tuple containing the model XML string and a dict of assets."""
  return common.read_model('reacher.xml'), common.ASSETS


@SUITE.add('benchmarking', 'easy')
def easy(time_limit=_DEFAULT_TIME_LIMIT, random=None, environment_kwargs=None):
  """Returns reacher with sparse reward with 5e-2 tol and randomized target."""
  physics = Physics.from_xml_string(*get_model_and_assets())
  task = Reacher(target_size=_BIG_TARGET, random=random)
  environment_kwargs = environment_kwargs or {}
  return control.Environment(
      physics, task, time_limit=time_limit, **environment_kwargs)


@SUITE.add('benchmarking')
def hard(time_limit=_DEFAULT_TIME_LIMIT, random=None, environment_kwargs=None):
  """Returns reacher with sparse reward with 1e-2 tol and randomized target."""
  physics = Physics.from_xml_string(*get_model_and_assets())
  task = Reacher(target_size=_SMALL_TARGET, random=random)
  environment_kwargs = environment_kwargs or {}
  return control.Environment(
      physics, task, time_limit=time_limit, **environment_kwargs)


class Physics(mujoco.Physics):
  """Physics simulation with additional features for the Reacher domain."""

  def finger_to_target(self):
    """Returns the vector from target to finger in global coordinates."""
    return (self.named.data.geom_xpos['target', :2] -
            self.named.data.geom_xpos['finger', :2])

  def finger_to_target_dist(self):
    """Returns the signed distance between the finger and target surface."""
    return np.linalg.norm(self.finger_to_target())


class Reacher(base.Task):
  """A reacher `Task` to reach the target."""

  def __init__(self, target_size, random=None):
    """Initialize an instance of `Reacher`.

    Args:
      target_size: A `float`, tolerance to determine whether finger reached the
          target.
      random: Optional, either a `numpy.random.RandomState` instance, an
        integer seed for creating a new `RandomState`, or None to select a seed
        automatically (default).
    """
    self._target_size = target_size
    super(Reacher, self).__init__(random=random)

  # def initialize_episode(self, physics):
  #   """Sets the state of the environment at the start of each episode."""
  #   physics.named.model.geom_size['target', 0] = self._target_size
  #   randomizers.randomize_limited_and_rotational_joints(physics, self.random)

  #   # Randomize target position
  #   angle = self.random.uniform(0, 2 * np.pi)
  #   radius = self.random.uniform(.05, .20)
  #   physics.named.model.geom_pos['target', 'x'] = radius * np.sin(angle)
  #   physics.named.model.geom_pos['target', 'y'] = radius * np.cos(angle)
    
  #   super(Reacher, self).initialize_episode(physics)

  # def get_observation(self, physics):
  #   """Returns an observation of the state and the target position."""
  #   obs = collections.OrderedDict()
  #   obs['position'] = physics.position()
  #   obs['to_target'] = physics.finger_to_target()
  #   obs['velocity'] = physics.velocity()
  #   return obs

  # def get_reward(self, physics):
  #   radii = physics.named.model.geom_size[['target', 'finger'], 0].sum()
  #   return rewards.tolerance(physics.finger_to_target_dist(), (0, radii))


  def initialize_episode(self, physics):
    """Sets the state of the environment at the start of each episode."""
    physics.named.model.geom_size['target', 0] = self._target_size
    randomizers.randomize_limited_and_rotational_joints(physics, self.random)
    self.bouncing = False
    self.rotation = True
    # Randomize target position
    self.angle = self.random.uniform(0, 2 * np.pi)
    self.radius = self.random.uniform(.05, .20)
    physics.named.model.geom_pos['target', 'x'] = self.radius * np.sin(self.angle)
    physics.named.model.geom_pos['target', 'y'] = self.radius * np.cos(self.angle)

    if self.rotation:
      self.omega = self.random.uniform(-0.05 * np.pi, 0.05 * np.pi)
    if self.bouncing:
      self.vx = self.random.uniform(-0.01, 0.01)
      self.vy = self.random.uniform(-0.01, 0.01)
    super(Reacher, self).initialize_episode(physics)

  def get_observation(self, physics):
    """Returns an observation of the state and the target position."""
    obs = collections.OrderedDict()
    obs['position'] = physics.position()
    obs['to_target'] = physics.finger_to_target()
    obs['velocity'] = physics.velocity()
    return obs

  def get_reward(self, physics):
    if self.rotation:
      self.angle += self.omega
      if self.angle >= 2*np.pi:
        self.angle -= 2*np.pi
      physics.named.model.geom_pos['target', 'x'] = self.radius * np.sin(self.angle)
      physics.named.model.geom_pos['target', 'y'] = self.radius * np.cos(self.angle)
    if self.bouncing:
      x = physics.named.model.geom_pos['target', 'x']
      y = physics.named.model.geom_pos['target', 'y']
      x += self.vx
      y += self.vy
      if x > 0.2 or x < -0.2:
        self.vx = -self.vx
        x = 0.4 * (x/abs(x)) - x
      if y > 0.2 or y < -0.2:
        self.vy = -self.vy
        y = 0.4 * (y/abs(y)) - y
      physics.named.model.geom_pos['target', 'x'] = x
      physics.named.model.geom_pos['target', 'y'] = y

    radii = physics.named.model.geom_size[['target', 'finger'], 0].sum()
    return rewards.tolerance(physics.finger_to_target_dist(), (0, radii))
