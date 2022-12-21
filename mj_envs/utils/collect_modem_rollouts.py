""" =================================================
Copyright (C) 2018 Vikash Kumar
Author  :: Vikash Kumar (vikashplus@gmail.com)
Source  :: https://github.com/vikashplus/mj_envs
License :: Under Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0 Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
================================================= """

import gym
from mj_envs.utils.paths_utils import plot as plotnsave_paths
from mj_envs.utils.policies.rand_eef_policy import RandEEFPolicy
from mj_envs.utils.policies.heuristic_policy import HeuristicPolicy
from PIL import Image
from pathlib import Path
import click
import numpy as np
import pickle
import time
import os
import torch

DESC = '''
Helper script to examine an environment and associated policy for behaviors; \n
- either onscreen, or offscreen, or just rollout without rendering.\n
- save resulting paths as pickle or as 2D plots
USAGE:\n
    $ python examine_env.py --env_name door-v0 \n
    $ python examine_env.py --env_name door-v0 --policy my_policy.pickle --mode evaluation --episodes 10 \n
'''


# MAIN =========================================================
@click.command(help=DESC)
@click.option('-e', '--env_name', type=str, help='environment to load', required= True)
@click.option('-m', '--mode', type=str, help='exploration or evaluation mode for policy', default='evaluation')
@click.option('-s', '--seed', type=int, help='seed for generating environment instances', default=123)
@click.option('-r', '--render', type=click.Choice(['onscreen', 'offscreen', 'none']), help='visualize onscreen or offscreen', default='none')
@click.option('-c', '--camera_name', type=str, default=None, help=('Camera name for rendering'))
@click.option('-o', '--output_dir', type=str, default='./', help=('Directory to save the outputs'))
@click.option('-on', '--output_name', type=str, default=None, help=('The name to save the outputs as'))
@click.option('-n', '--num_rollouts', type=int, help='number of rollouts to save', default=100)
@click.option('-hw', '--is_hardware', type=bool, help='whether or not to run on real robot', default=False)
def main(env_name, mode, seed, render, camera_name, output_dir, output_name, num_rollouts, is_hardware):

    # seed and load environments
    np.random.seed(seed)
    env = gym.make(env_name, **{'reward_mode': 'sparse', 'is_hardware':is_hardware})
    env.seed(seed)

    pi = HeuristicPolicy(env, seed, is_hardware)
    output_name = 'heuristic'

    # resolve directory
    if (os.path.isdir(output_dir) == False):
        os.mkdir(output_dir)

    if (os.path.isdir(output_dir +'/frames') == False):
        os.mkdir(output_dir+'/frames')

    rollouts = 0
    successes = 0

    while successes < num_rollouts:

        if is_hardware:
            # Move arm out of camera's view
            start_action = [0.25, 0.5, 1.25, 3.14, 0, 0, 0.04, 0.04]
            env.step(start_action)
            time.sleep(3)

            # Detect and set the object pose
            env.real_obj_pos = [0.0, 0.5, 1.0]

        # examine policy's behavior to recover paths
        paths = env.examine_policy(
            policy=pi,
            horizon=env.spec.max_episode_steps,
            num_episodes=1,
            frame_size=(640,480),
            mode=mode,
            output_dir=output_dir+'/',
            filename=output_name,
            camera_name=camera_name,
            render=render)
        rollouts += 1

        # evaluate paths
        success_percentage = env.env.evaluate_success(paths)
        if success_percentage > 0.5:
            ro_fn = 'rollout'+f'{(successes+seed):010d}'

            data = {}
            data['states'] = paths[0]['observations'][:,:66]
            data['actions'] = paths[0]['actions']
            data['infos'] = [{'success': reward} for reward in paths[0]['rewards']]
            
            data['frames'] = []
            imgs = paths[0]['observations'][:,66:]
            imgs = imgs.reshape((data['states'].shape[0],-1,224,224,3))
            imgs = imgs.astype(np.uint8)
            for i in range(imgs.shape[0]):
                for j in range(imgs.shape[1]):
                    img_fn = ro_fn +'_cam'+str(j)+'_step'+f'{i:05d}'
                    img = Image.fromarray(imgs[i,j])
                    img.save(output_dir+'/frames/'+img_fn+'.png')
                    if imgs.shape[1] == 1 or j == 1: # First case if there's only one cam, second case corresponds to right_cam
                        # Record path in data
                        data['frames'].append(Path(img_fn+'.png'))
         
            torch.save(data, output_dir+'/'+ro_fn+'.pt')
            successes += 1

            print('Success {} ({}/{})'.format(successes/rollouts,successes,rollouts))

if __name__ == '__main__':
    main()