""" =================================================
Copyright (C) 2018 Vikash Kumar
Author  :: Vikash Kumar (vikashplus@gmail.com)
Source  :: https://github.com/vikashplus/mj_envs
License :: Under Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0 Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
================================================= """

import numpy as np
import os
import glob
import pickle
import h5py
import skvideo.io
from PIL import Image
import click
from mj_envs.utils.dict_utils import flatten_dict, dict_numpify

# Useful to check the horizon for teleOp / Hardware experiments
def plot_horizon(paths, env, fileName_prefix=None):
    import matplotlib as mpl
    mpl.use('TkAgg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 5})

    if "time" in paths[0]['env_infos']:
        horizon = np.zeros(len(paths))

        # plot timesteps
        plt.clf()

        rl_dt_ideal = env.env.frame_skip * env.env.model.opt.timestep
        for i, path in enumerate(paths):
            dt = path['env_infos']['time'][1:] - path['env_infos']['time'][:-1]
            horizon[i] = path['env_infos']['time'][-1] - path['env_infos'][
                'time'][0]
            h1 = plt.plot(
                path['env_infos']['time'][1:],
                dt,
                '-',
                label=('time=%1.2f' % horizon[i]))
        h1 = plt.plot(
            np.array([0, max(horizon)]),
            rl_dt_ideal * np.ones(2),
            'g', alpha=.5,
            linewidth=2.0)

        plt.legend([h1[0]], ['ideal'], loc='upper right')
        plt.ylabel('time step (sec)')
        plt.xlabel('time (sec)')
        plt.ylim(rl_dt_ideal - 0.005, rl_dt_ideal + .005)
        plt.suptitle('Timestep profile for %d rollouts' % len(paths))

        file_name = fileName_prefix + '_timesteps.pdf'
        plt.savefig(file_name)
        print("Saved:", file_name)

        # plot horizon
        plt.clf()
        h1 = plt.plot(
            np.array([0, len(paths)]),
            env.horizon * rl_dt_ideal * np.ones(2),
            'g',
            linewidth=5.0,
            label='ideal')
        plt.bar(np.arange(0, len(paths)), horizon, label='observed')
        plt.ylabel('rollout duration (sec)')
        plt.xlabel('rollout id')
        plt.legend()
        plt.suptitle('Horizon distribution for %d rollouts' % len(paths))

        file_name = fileName_prefix + '_horizon.pdf'
        plt.savefig(file_name)
        print("Saved:", file_name)


# Plot paths to a pdf file
def plot(paths, env=None, fileName_prefix=''):
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 5})

    for i, path in enumerate(paths):
        plt.clf()

        # observations
        nplt1 = len(path['env_infos']['obs_dict'])
        for iplt1, key in enumerate(
                sorted(path['env_infos']['obs_dict'].keys())):
            ax = plt.subplot(nplt1, 2, iplt1 * 2 + 1)
            if iplt1 != (nplt1 - 1):
                ax.axes.xaxis.set_ticklabels([])
            if iplt1 == 0:
                plt.title('Observations')
            ax.yaxis.tick_right()
            plt.plot(
                path['env_infos']['time'],
                path['env_infos']['obs_dict'][key],
                label=key)
            # plt.ylabel(key)
            plt.text(0.01, .01, key, transform=ax.transAxes)
        plt.xlabel('time (sec)')

        # actions
        nplt2 = 3
        ax = plt.subplot(nplt2, 2, 2)
        ax.set_prop_cycle(None)
        # h4 = plt.plot(path['env_infos']['time'], env.env.act_mid + path['actions']*env.env.act_rng, '-', label='act') # plot scaled actions
        h4 = plt.plot(
            path['env_infos']['time'], path['actions'], '-',
            label='act')  # plot normalized actions
        plt.ylabel('actions')
        ax.axes.xaxis.set_ticklabels([])
        ax.yaxis.tick_right()

        # rewards/ scores
        if "score" in path['env_infos']:
            ax = plt.subplot(nplt2, 2, 6)
            plt.plot(
                path['env_infos']['time'],
                path['env_infos']['score'],
                label='score')
            plt.xlabel('time')
            plt.ylabel('score')
            ax.yaxis.tick_right()

        if "rwd_dict" in path['env_infos']:
            ax = plt.subplot(nplt2, 2, 4)
            ax.set_prop_cycle(None)
            for key in sorted(path['env_infos']['rwd_dict'].keys()):
                plt.plot(
                    path['env_infos']['time'],
                    path['env_infos']['rwd_dict'][key],
                    label=key)
            plt.legend(
                loc='upper left',
                fontsize='x-small',
                bbox_to_anchor=(.75, 0.25),
                borderaxespad=0.)
            ax.axes.xaxis.set_ticklabels([])
            plt.ylabel('rewards')
            ax.yaxis.tick_right()
        if env and hasattr(env.env, "rwd_keys_wt"):
            ax = plt.subplot(nplt2, 2, 6)
            ax.set_prop_cycle(None)
            for key in env.env.rwd_keys_wt.keys():
                plt.plot(
                    path['env_infos']['time'],
                    path['env_infos']['rwd_dict'][key]*env.env.rwd_keys_wt[key],
                    label=key)
            plt.legend(
                loc='upper left',
                fontsize='x-small',
                bbox_to_anchor=(.75, 0.25),
                borderaxespad=0.)
            ax.axes.xaxis.set_ticklabels([])
            plt.ylabel('wt*rewards')
            ax.yaxis.tick_right()

        file_name = fileName_prefix + '_path' + str(i) + '.pdf'
        plt.savefig(file_name)
        print("saved ", file_name)


# render frames/videos from paths
def render(rollout_path, render_format:str="mp4", cam_name:str="left"):
    # rollout_path:     Absolute path of the rollout (h5/pickle)', default=None
    # format:           Format to save. Choice['rgb', 'mp4']
    # cam:              Camera to render. Example ['left', 'right', 'top', 'Franka_wrist']

    output_dir = os.path.dirname(rollout_path)
    rollout_name = os.path.split(rollout_path)[-1]
    output_name, output_type = os.path.splitext(rollout_name)


    if output_type=='.h5':
        paths = h5py.File(rollout_path, 'r')
    elif output_type=='.pickle':
        paths = pickle.load(open(rollout_path, 'rb'))
    else:
        raise TypeError("Unknown path format. Check file")


    # Run through all trajs in the paths
    for i_path, path in enumerate(paths):
        if output_type=='.h5':
            path = paths[path]

        # find full path name
        if i_path == 0:
            for key in path['env_infos']['obs_dict'].keys():
                if cam_name in key:
                    cam_name = key
                    break

        # find find horizon
        path_horizon = path['actions'].shape[0]

        # render video
        if render_format == "mp4":
            # pre allocate buffer
            if i_path == 0:
                height, width, _ = path['env_infos']['obs_dict'][cam_name][0].shape
                frames = np.zeros((path_horizon, height, width, 3), dtype=np.uint8)

            file_name = os.path.join(output_dir, output_name+'{}{}.mp4'.format(i_path, cam_name))
            print("Recovering frames:", end="")
            for t in range(path_horizon):
                frames[t,:,:,:] = path['env_infos']['obs_dict'][cam_name][t]
                print(t, end=",")
            frames[frames==255] = 254 # remove rendering artifact due to saturation
            skvideo.io.vwrite(file_name, np.asarray(frames))
            print("\nSaving: {}".format(file_name))

        # render each frame
        elif render_format == "rgb":
            print("Recovering frames:", end="")
            for t in range(path_horizon):
                file_name = os.path.join(output_dir, output_name+'{}{}{}.png'.format(i_path, cam_name, t))
                img =  path['env_infos']['obs_dict'][cam_name][t]
                image = Image.fromarray(img)
                image.save(file_name)
                print(t, end=",")
            print(": Done")
        else:
            raise TypeError("Unknown format")


# parse path from robohive format into robopen dataset format
def path2dataset(path:dict)->dict:
    """
    Convery Robohive path.pickle format into robopen dataset format
    """

    obs_keys = path['env_infos']['obs_dict'].keys()
    dataset = {}
    # Data =====
    dataset['data/time'] = path['env_infos']['obs_dict']['t']

    # actions
    if 'actions' in path.keys():
        dataset['data/ctrl_arm'] = path['actions'][:,:7]
        dataset['data/ctrl_ee'] = path['actions'][:,7:]

    # states
    for key in ['qp_arm', 'qv_arm', 'tau_arm', 'qp_ee', 'qv_ee']:
        if key in obs_keys:
            dataset['data/'+key] = path['env_infos']['obs_dict'][key]

    # cams
    for cam in ['left', 'right', 'top', 'wrsit']:
        for key in obs_keys:
            if 'rgb:'+cam in key:
                dataset['data/rgb_'+cam] = path['env_infos']['obs_dict'][key]
            if 'd:'+cam in key:
                dataset['data/d_'+cam] = path['env_infos']['obs_dict'][key]
    # user
    if 'user_input' in obs_keys:
        dataset['data/user_input'] = path['env_infos']['obs_dict']['user_input']

    # Derived =====
    if 'pos_ee' in obs_keys:
        dataset['derived/pos_ee'] = path['env_infos']['obs_dict']['pos_ee']
    if 'rot_ee' in obs_keys:
        dataset['derived/rot_ee'] = path['env_infos']['obs_dict']['rot_ee']

    return dataset


# convert paths from pickle to h5 format
def pickle2h5(rollout_path, output_dir=None, verify_output=False, h5_format:str='path', compress_path=False):
    # path:         single path or folder with paths
    # output_dir:   Directory to save the outputs. use path location if none.
    # verify:       Verify the saved file

   # resolve output dirzz
    if output_dir == None: # overide the default
        output_dir = os.path.dirname(rollout_path)

    # resolve rollout_paths
    if os.path.isfile(rollout_path):
        rollout_paths = [rollout_path]
    else:
        rollout_paths = glob.glob(os.path.join(rollout_path, '*.pickle'))

    # Parse all rollouts
    for rollout_path in rollout_paths:

        # parse all paths
        print('Parsing: ', rollout_path)

        paths = pickle.load(open(rollout_path, 'rb'))
        rollout_name = os.path.split(rollout_path)[-1]
        output_name = os.path.splitext(rollout_name)[0]
        output_path = os.path.join(output_dir, output_name + '.h5')

        paths_h5 = h5py.File(output_path, "w")

        # Robohive path format
        if h5_format == "path":
            for i_path, path in enumerate(paths):
                print("parsing rollout", i_path)
                trial = paths_h5.create_group('Trial'+str(i_path))
                # remove duplicate infos
                if compress_path:
                    if 'observations' in path.keys():
                        del path['observations']
                    if 'state' in path['env_infos'].keys():
                        del path['env_infos']['state']
                # flatten dict and fix resolutions
                path = flatten_dict(data=path)
                path = dict_numpify(path, u_res=None, i_res=None, f_res=np.float16)
                # add trail
                for k, v in path.items():
                    trial.create_dataset(k, data=v, compression='gzip', compression_opts=4)

        # RoboPen dataset format
        elif h5_format == "dataset":
            for i_path, path in enumerate(paths):
                print("parsing rollout", i_path)
                trial = paths_h5.create_group('Trial'+str(i_path))
                dataset = path2dataset(path) # convert to robopen dataset format
                dataset = dict_numpify(dataset, u_res=None, i_res=None, f_res=np.float16) # numpify + data resolutions
                for k, v in dataset.items():
                    trial.create_dataset(k, data=v, compression='gzip', compression_opts=4)

        else:
            TypeError('Unsupported h5_format')

        # close the h5 writer for this path
        print('Saving:  ', output_path)

        # Read back and verify a few keys
        if verify_output:

            def allkeys(obj):
                    "Recursively find all keys in an h5py.Group."
                    keys = (obj.name,)
                    if isinstance(obj, h5py.Group):
                        for key, value in obj.items():
                            if isinstance(value, h5py.Group):
                                keys = keys + allkeys(value)
                            else:
                                print("\t", value.name, "\t\t", value)
                                keys = keys + (value.name,)
                    return keys

            with h5py.File(output_path, "r") as h5file:
                print("Printing schema read from output: ", output_path)
                keys = allkeys(h5file['Trial0'])

    print("Finished Processing")


DESC="""
Script to recover images and videos from the saved pickle files
 - python utils/render_paths.py -p  paths.pickle -f mp4 -c right
 - python utils/render_paths.py -p  paths.h5 -f rgb -c left
"""
@click.command(help=DESC)
@click.option('-u', '--util', type=click.Choice(['plot_horizon', 'plot', 'render', 'pickle2h5']), help='pick utility', required=True)
@click.option('-p', '--path', type=str, help='absolute path of the rollout (h5/pickle)', default=None)
@click.option('-e', '--env', type=str, help='Env name', default=None)
@click.option('-on', '--output_name', type=str, default=None, help=('Output name'))
@click.option('-od', '--output_dir', type=str, default=None, help=('Directory to save the outputs'))
@click.option('-vo', '--verify_output', type=bool, default=False, help=('Verify the saved file'))
@click.option('-hf', '--h5_format', type=click.Choice(['path', 'dataset']), help='format to save', default="path")
@click.option('-cp', '--compress_path', help='compress paths. Remove obs and env_info/state keys', default=False)
@click.option('-rf', '--render_format', type=click.Choice(['rgb', 'mp4']), help='format to save', default="mp4")
@click.option('-cn', '--cam_name', help='camera to render. Eg: left, right, top, Franka_wrist', default="left")
def util_path_cli(util, path, env, output_name, output_dir, verify_output, render_format, cam_name,h5_format, compress_path):

    if util=='plot_horizon':
        fileName_prefix = os.join(output_dir, output_name)
        plot_horizon(path, env, fileName_prefix)
    elif util=='plot':
        fileName_prefix = os.join(output_dir, output_name)
        plot(path, env, fileName_prefix)
    elif util=='render':
        render(rollout_path=path, render_format=render_format, cam_name=cam_name)
    elif util=='pickle2h5':
        pickle2h5(rollout_path=path, output_dir=output_dir, verify_output=verify_output, h5_format=h5_format, compress_path=compress_path)
    else:
        raise TypeError("Unknown utility requested")


if __name__ == '__main__':
    util_path_cli()