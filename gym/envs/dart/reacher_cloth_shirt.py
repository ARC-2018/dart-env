# This environment is created by Alexander Clegg (alexanderwclegg@gmail.com)

import numpy as np
from gym import utils
from gym.envs.dart.dart_cloth_env import *
import random
import time

from pyPhysX.colors import *
import pyPhysX.pyutils as pyutils

import OpenGL.GL as GL
import OpenGL.GLU as GLU
import OpenGL.GLUT as GLUT

''' This env is setup for upper body single arm reduced action space learning with draped shirt'''

class DartClothShirtReacherEnv(DartClothEnv, utils.EzPickle):
    def __init__(self):
        self.target = np.array([0.8, -0.6, 0.6])
        
        #22 dof upper body
        self.action_scale = np.ones(11)*10
        self.control_bounds = np.array([np.ones(11), np.ones(11)*-1])
        
        self.doSettle = False
        self.settlePeriod = 50
        self.doInterpolation = False 
        self.interpolationPeriod = 200
        self.interpolationGoal = np.zeros(22)
        self.interpolationStart = np.zeros(22)
        self.numSteps = 0 #increments every step, 0 on reset
        
        #create cloth scene
        clothScene = pyphysx.ClothScene(step=0.01, mesh_path="/home/alexander/Documents/dev/dart-env/gym/envs/dart/assets/tshirt_m.obj", scale = 1.6)
        clothScene.togglePinned(0,0) #turn off auto-bottom pin
        #clothScene.togglePinned(0,9)
        #clothScene.togglePinned(0,10)
        #clothScene.togglePinned(0,37)
        #clothScene.togglePinned(0,42)
        #clothScene.togglePinned(0,44)
        #clothScene.togglePinned(0,48)
        #clothScene.togglePinned(0,51)
        #clothScene.togglePinned(0,54)
        #clothScene.togglePinned(0,58)
        #clothScene.togglePinned(0,64)
        
        '''clothScene.togglePinned(0,111) #collar
        clothScene.togglePinned(0,113) #collar
        clothScene.togglePinned(0,117) #collar
        clothScene.togglePinned(0,193) #collar
        clothScene.togglePinned(0,112) #collar
        clothScene.togglePinned(0,114) #collar
        clothScene.togglePinned(0,115) #collar
        clothScene.togglePinned(0,116) #collar
        clothScene.togglePinned(0,192) #collar
        clothScene.togglePinned(0,191) #collar'''
        
        '''clothScene.togglePinned(0,190) #collar
        clothScene.togglePinned(0,189) #collar
        clothScene.togglePinned(0,188) #collar
        clothScene.togglePinned(0,187) #collar
        clothScene.togglePinned(0,186) #collar
        clothScene.togglePinned(0,110) #collar
        clothScene.togglePinned(0,109) #collar
        clothScene.togglePinned(0,108) #collar
        clothScene.togglePinned(0,107) #collar'''
        
        
        #clothScene.togglePinned(0,144) #bottom
        #clothScene.togglePinned(0,147) #bottom
        #clothScene.togglePinned(0,149) #bottom
        #clothScene.togglePinned(0,153) #bottom
        #clothScene.togglePinned(0,155) #bottom
        #clothScene.togglePinned(0,161) #bottom
        #clothScene.togglePinned(0,165) #bottom
        #clothScene.togglePinned(0,224) #right sleeve
        #clothScene.togglePinned(0,229) #right sleeve
        #clothScene.togglePinned(0,233) #right sleeve
        #clothScene.togglePinned(0,236) #sleeve
        #clothScene.togglePinned(0,240) #sleeve
        #clothScene.togglePinned(0,246) #sleeve
        
        '''clothScene.togglePinned(0,250) #left sleeve
        clothScene.togglePinned(0,253) #left sleeve
        clothScene.togglePinned(0,257) #left sleeve
        clothScene.togglePinned(0,259) #left sleeve
        clothScene.togglePinned(0,262) #left sleeve
        clothScene.togglePinned(0,264) #left sleeve'''
        
        
        #intialize the parent env
        #DartClothEnv.__init__(self, cloth_scene=clothScene, model_paths='UpperBodyCapsules.skel', frame_skip=4, observation_size=(66+66+6), action_bounds=self.control_bounds)
        DartClothEnv.__init__(self, cloth_scene=clothScene, model_paths='UpperBodyCapsules.skel', frame_skip=4, observation_size=(66+66+6), action_bounds=self.control_bounds, visualize=False)
        
        #TODO: additional observation size for force
        utils.EzPickle.__init__(self)
        
        self.clothScene.seedRandom(random.randint(1,1000))
        self.clothScene.setFriction(0, 0.6)
        
        self.updateClothCollisionStructures(capsules=True, hapticSensors=True)
        
        self.simulateCloth = True
        self.sampleFromHemisphere = True
        self.rotateCloth = False
        self.randomRoll = False
        
        self.trackSuccess = False
        self.renderSuccess = False
        self.targetHistory = []
        self.successHistory = []
        
        self.renderDofs = True #if true, show dofs text 
        self.renderForceText = False
        
        self.random_dir = np.array([0,0,1.])
        
        self.reset_number = 0 #debugging
        print("done init")

    def limits(self, dof_ix):
        return np.array([self.robot_skeleton.dof(dof_ix).position_lower_limit(), self.robot_skeleton.dof(dof_ix).position_upper_limit()])
        
    def poseInterpolate(self, q0, q1, t):
        'interpolate the pose q0->q1 over t=[0,1]'
        qpos = LERP(q0,q1,t)
        self.robot_skeleton.set_positions(qpos)
        
    def saveObjState(self):
        print("Trying to save the object state")
        self.clothScene.saveObjState("objState", 0)
        
    def loadObjState(self):
        self.clothScene.loadObjState("objState", 0)
        
    def _step(self, a):
        clamped_control = np.array(a)
        for i in range(len(clamped_control)):
            if clamped_control[i] > self.control_bounds[0][i]:
                clamped_control[i] = self.control_bounds[0][i]
            if clamped_control[i] < self.control_bounds[1][i]:
                clamped_control[i] = self.control_bounds[1][i]
        tau = np.multiply(clamped_control, self.action_scale)

        #fingertip = np.array([0.0, -0.25, 0.0])
        fingertip = np.array([0.0, -0.06, 0.0])
        wFingertip1 = self.robot_skeleton.bodynodes[8].to_world(fingertip)
        vec1 = self.target-wFingertip1
        
        #execute special actions
        if self.doSettle and self.numSteps<self.settlePeriod:
            tau = np.zeros(len(tau))
        elif self.doInterpolation:
            t = self.numSteps/self.interpolationPeriod
            if self.doSettle:
                t = (self.numSteps-self.settlePeriod)/self.interpolationPeriod
            if t < 1:
                tau = np.zeros(len(tau))
                self.poseInterpolate(self.interpolationStart, self.interpolationGoal, t)
            elif t<1.1:
                print(t)
        
        #apply action and simulate
        tau = np.concatenate([tau, np.zeros(11)])
        self.do_simulation(tau, self.frame_skip)
        
        wFingertip2 = self.robot_skeleton.bodynodes[8].to_world(fingertip)
        vec2 = self.target-wFingertip2
        
        reward_dist = - np.linalg.norm(vec2)
        reward_ctrl = - np.square(tau).sum() * 0.001
        reward_progress = np.dot((wFingertip2 - wFingertip1), vec1/np.linalg.norm(vec1)) * 100
        alive_bonus = -0.001
        reward_prox = 0
        #if -reward_dist < 0.1:
        #    reward_prox += (0.1+reward_dist)*10
        reward = reward_ctrl + alive_bonus + reward_progress + reward_prox
        #reward = reward_dist + reward_ctrl
        
        ob = self._get_obs()

        s = self.state_vector()
        
        #update physx capsules
        self.updateClothCollisionStructures(hapticSensors=True)
        
        #check cloth deformation for termination
        clothDeformation = 0
        if self.simulateCloth is True:
            clothDeformation = self.clothScene.getMaxDeformationRatio(0)
        
        #check termination conditions
        done = False
        if not np.isfinite(s).all():
            done = True
            reward -= 500
        elif -reward_dist < 0.1:
            done = True
            reward += 100
        elif (clothDeformation > 15):
            if not self.doSettle or self.numSteps>self.settlePeriod:
                done = True
                reward -= 500
        
        self.numSteps += 1

        return ob, reward, done, {}

    def _get_obs(self):
        '''get_obs'''
        f_size = 66
        theta = self.robot_skeleton.q
        #fingertip = np.array([0.0, -0.25, 0.0])
        fingertip = np.array([0.0, -0.06, 0.0])
        vec = self.robot_skeleton.bodynodes[8].to_world(fingertip) - self.target
        
        if self.simulateCloth is True:
            f = self.clothScene.getHapticSensorObs()#get force from simulation 
        else:
            f = np.zeros(f_size)
        
        #print("ID getobs:" + str(self.clothScene.id))
        #print("f: " + str(f))
        #print("len f = " + str(len(f)))
        return np.concatenate([np.cos(theta), np.sin(theta), self.robot_skeleton.dq, vec, self.target, f]).ravel()
        #return np.concatenate([theta, self.robot_skeleton.dq, vec]).ravel()

    def reset_model(self):
        '''reset_model'''
        self.numSteps = 0
        #self.clothScene.translateCloth(0, np.array([0,3.1,0]))
        self.dart_world.reset()
        self.clothScene.reset()
        qpos = self.robot_skeleton.q + self.np_random.uniform(low=-.015, high=.015, size=self.robot_skeleton.ndofs)
        qpos[0] -= 0
        qpos[1] -= 0.
        qpos[2] += 0
        qpos[3] += 0.
        qpos[4] -= 0.
        #qpos[5] += 1
        qpos[5] += 0.75
        qpos[6] += 0.25
        #qpos[7] += 0.0
        qpos[7] += 2.0
        qpos[8] += 2.9
        qpos[9] += 0.6
        qpos[10] += 0.0
        
        self.interpolationStart = np.array(qpos)
        self.interpolationGoal = np.array(qpos)
        self.interpolationGoal[5] = 0.75
        self.interpolationGoal[6] = 0.25
        self.interpolationGoal[7] = 2.0
        self.interpolationGoal[8] = 2.9
        self.interpolationGoal[9] = 0.6
        
        #uper body 1 arm fail #1 settings
        '''qpos[7] += 0.25
        qpos[8] += 2.0
        qpos[9] += 0.0
        qpos[10] += -0.6'''

        qvel = self.robot_skeleton.dq + self.np_random.uniform(low=-.025, high=.025, size=self.robot_skeleton.ndofs)
        self.set_state(qpos, qvel)
        
        #reset cloth tube orientation and rotate sphere position
        v1 = np.array([0,1.,0])
        v2 = np.array([0.,0,-1.])
        self.random_dir = np.array([-1.,0,0])
        if self.simulateCloth is True:   
            if self.rotateCloth is True:
                while True:
                    v2 = self.clothScene.sampleDirections()[0]
                    if np.dot(v2/np.linalg.norm(v2), np.array([0,-1,0.])) < 1:
                        break
            M = self.clothScene.rotateTo(v1,v2)
            self.clothScene.rotateCloth(0, M)
            self.clothScene.rotateCloth(0, self.clothScene.getRotationMatrix(a=0.25, axis=np.array([0,1.,0.])))
            #self.clothScene.translateCloth(0, np.array([-0.042,-0.6,-0.025]))
            self.clothScene.translateCloth(0, np.array([-0.042,-0.7,-0.035]))
        #self.clothScene.translateCloth(0, np.array([-0.75,0,0]))
        #self.clothScene.translateCloth(0, np.array([0,3.1,0]))
        #self.clothScene.rotateCloth(0, self.clothScene.getRotationMatrix(a=random.uniform(0, 6.28), axis=np.array([0,0,1.])))
        #self.clothScene.rotateCloth(0, M)
        
        #load cloth state from ~/Documents/dev/objFile.obj
        self.clothScene.loadObjState()
        
        #move cloth out of arm range
        #self.clothScene.translateCloth(0, np.array([-10.5,0,0]))
        
        #old sampling in box
        #'''
        reacher_range = 0.95
        if not self.sampleFromHemisphere:
            while True:
                self.target = self.np_random.uniform(low=-reacher_range, high=reacher_range, size=3)
                #print('target = ' + str(self.target))
                if np.linalg.norm(self.target) < reacher_range: break
        #'''
        
        #sample target from hemisphere
        if self.sampleFromHemisphere is True:
            self.target = self.hemisphereSample(maxradius=reacher_range, minradius=0.7, norm=self.random_dir)

        self.dart_world.skeletons[0].q=[0, 0, 0, self.target[0], self.target[1], self.target[2]]

        #update physx capsules
        self.updateClothCollisionStructures(hapticSensors=True)
        self.clothScene.clearInterpolation()

        #debugging
        self.reset_number += 1
        
        obs = self._get_obs()
        
        #self.render()
        #if np.linalg.norm(obs[-39:]) > 0.00001:
        #    print("COLLISION")
        #    self.reset_model()

        return self._get_obs()

    def updateClothCollisionStructures(self, capsules=False, hapticSensors=False):
        a=0
        #collision spheres creation
        fingertip = np.array([0.0, -0.06, 0.0])
        z = np.array([0.,0,0])
        cs0 = self.robot_skeleton.bodynodes[1].to_world(z)
        cs1 = self.robot_skeleton.bodynodes[2].to_world(z)
        cs2 = self.robot_skeleton.bodynodes[16].to_world(z)
        cs3 = self.robot_skeleton.bodynodes[16].to_world(np.array([0,0.175,0]))
        cs4 = self.robot_skeleton.bodynodes[4].to_world(z)
        cs5 = self.robot_skeleton.bodynodes[6].to_world(z)
        cs6 = self.robot_skeleton.bodynodes[7].to_world(z)
        cs7 = self.robot_skeleton.bodynodes[8].to_world(z)
        cs8 = self.robot_skeleton.bodynodes[8].to_world(fingertip)
        cs9 = self.robot_skeleton.bodynodes[10].to_world(z)
        cs10 = self.robot_skeleton.bodynodes[12].to_world(z)
        cs11 = self.robot_skeleton.bodynodes[13].to_world(z)
        cs12 = self.robot_skeleton.bodynodes[14].to_world(z)
        cs13 = self.robot_skeleton.bodynodes[14].to_world(fingertip)
        csVars0 = np.array([0.15, -1, -1, 0,0,0])
        csVars1 = np.array([0.07, -1, -1, 0,0,0])
        csVars2 = np.array([0.1, -1, -1, 0,0,0])
        csVars3 = np.array([0.1, -1, -1, 0,0,0])
        csVars4 = np.array([0.065, -1, -1, 0,0,0])
        csVars5 = np.array([0.05, -1, -1, 0,0,0])
        csVars6 = np.array([0.0365, -1, -1, 0,0,0])
        csVars7 = np.array([0.04, -1, -1, 0,0,0])
        csVars8 = np.array([0.046, -1, -1, 0,0,0])
        csVars9 = np.array([0.065, -1, -1, 0,0,0])
        csVars10 = np.array([0.05, -1, -1, 0,0,0])
        csVars11 = np.array([0.0365, -1, -1, 0,0,0])
        csVars12 = np.array([0.04, -1, -1, 0,0,0])
        csVars13 = np.array([0.036, -1, -1, 0,0,0])
        collisionSpheresInfo = np.concatenate([cs0, csVars0, cs1, csVars1, cs2, csVars2, cs3, csVars3, cs4, csVars4, cs5, csVars5, cs6, csVars6, cs7, csVars7, cs8, csVars8, cs9, csVars9, cs10, csVars10, cs11, csVars11, cs12, csVars12, cs13, csVars13]).ravel()
        #collisionSpheresInfo = np.concatenate([cs0, csVars0, cs1, csVars1]).ravel()
        
        self.clothScene.setCollisionSpheresInfo(collisionSpheresInfo)
        
        if capsules is True:
            #collision capsules creation
            collisionCapsuleInfo = np.zeros((14,14))
            collisionCapsuleInfo[0,1] = 1
            collisionCapsuleInfo[1,2] = 1
            collisionCapsuleInfo[1,4] = 1
            collisionCapsuleInfo[1,9] = 1
            collisionCapsuleInfo[2,3] = 1
            collisionCapsuleInfo[4,5] = 1
            collisionCapsuleInfo[5,6] = 1
            collisionCapsuleInfo[6,7] = 1
            collisionCapsuleInfo[7,8] = 1
            collisionCapsuleInfo[9,10] = 1
            collisionCapsuleInfo[10,11] = 1
            collisionCapsuleInfo[11,12] = 1
            collisionCapsuleInfo[12,13] = 1
            self.clothScene.setCollisionCapsuleInfo(collisionCapsuleInfo)
            
        if hapticSensors is True:
            hapticSensorLocations = np.concatenate([cs0, cs1, cs2, cs3, cs4, LERP(cs4, cs5, 0.33), LERP(cs4, cs5, 0.66), cs5, LERP(cs5, cs6, 0.33), LERP(cs5,cs6,0.66), cs6, cs7, cs8, cs9, LERP(cs9, cs10, 0.33), LERP(cs9, cs10, 0.66), cs10, LERP(cs10, cs11, 0.33), LERP(cs10, cs11, 0.66), cs11, cs12, cs13])
            self.clothScene.setHapticSensorLocations(hapticSensorLocations)
            
    def getViewer(self, sim, title=None, extraRenderFunc=None, inputFunc=None):
        return DartClothEnv.getViewer(self, sim, title, self.extraRenderFunction, self.inputFunc)
        
    def hemisphereSample(self, maxradius=1, minradius = 0, norm=np.array([0,0,1.]), frustrum = 0.7):
        p = norm
        while True:
            p = self.np_random.uniform(low=-maxradius, high=maxradius, size=3)
            p_n = np.linalg.norm(p)
            if p_n <= maxradius and p_n >= minradius:
                if(np.dot(p/p_n, norm) > frustrum):
                    return p

        
    def extraRenderFunction(self):
        #print("extra render function")
        
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3d(0,0,0)
        GL.glVertex3d(-1,0,0)
        GL.glEnd()
        
        if self.renderSuccess is True:
            for i in range(len(self.targetHistory)):
                p = self.targetHistory[i]
                s = self.successHistory[i]
                GL.glColor3d(1,0.,0)
                if s is True:
                    GL.glColor3d(0,1.,0)
                GL.glPushMatrix()
                GL.glTranslated(p[0], p[1], p[2])
                GLUT.glutSolidSphere(0.01, 10,10)
                GL.glPopMatrix()
        
        #draw hemisphere samples for target sampling
        '''
        GL.glColor3d(0,1,0)
        for i in range(1000):
            normVec = self.random_dir
            p = self.hemisphereSample(maxradius=0.95, minradius=0.7, norm=normVec)

            #p=np.array([0,0,0.])
            #while True:
            #    p = self.np_random.uniform(low=-1.5, high=1.5, size=3)
            #    if np.linalg.norm(p) < 1.5: break
            GL.glPushMatrix()
            GL.glTranslated(p[0], p[1], p[2])
            GLUT.glutSolidSphere(0.01, 10,10)
            GL.glPopMatrix()
        '''
        
        #print("ID:" + str(self.clothScene.id))
            
        m_viewport = GL.glGetIntegerv(GL.GL_VIEWPORT)
        
        textX = 15.
        if self.renderForceText:
            HSF = self.clothScene.getHapticSensorObs()
            #print("HSF: " + str(HSF))
            for i in range(self.clothScene.getNumHapticSensors()):
                #print("i = " + str(i))
                #print("HSL[i] = " + str(HSL[i*3:i*3+3]))
                #print("HSF[i] = " + str(HSF[i*3:i*3+3]))
                self.clothScene.drawText(x=textX, y=60.+15*i, text="||f[" + str(i) + "]|| = " + str(np.linalg.norm(HSF[3*i:3*i+3])), color=(0.,0,0))
            textX += 160
        
        #draw 2d HUD setup
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0, m_viewport[2], 0, m_viewport[3], -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glDisable(GL.GL_CULL_FACE);
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT);
        
        #draw the load bars
        if self.renderDofs:
            #draw the load bar outlines
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
            GL.glColor3d(0,0,0)
            GL.glBegin(GL.GL_QUADS)
            for i in range(len(self.robot_skeleton.q)):
                y = 58+18.*i
                x0 = 120+70
                x1 = 210+70
                GL.glVertex2d(x0, y)
                GL.glVertex2d(x0, y+15)
                GL.glVertex2d(x1, y+15)
                GL.glVertex2d(x1, y)
            GL.glEnd()
            #draw the load bar fills
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)
            for i in range(len(self.robot_skeleton.q)):
                qlim = self.limits(i)
                qfill = (self.robot_skeleton.q[i]-qlim[0])/(qlim[1]-qlim[0])
                y = 58+18.*i
                x0 = 121+70
                x1 = 209+70
                x = LERP(x0,x1,qfill)
                xz = LERP(x0,x1,(-qlim[0])/(qlim[1]-qlim[0]))
                GL.glColor3d(0,2,3)
                GL.glBegin(GL.GL_QUADS)
                GL.glVertex2d(x0, y+1)
                GL.glVertex2d(x0, y+14)
                GL.glVertex2d(x, y+14)
                GL.glVertex2d(x, y+1)
                GL.glEnd()
                GL.glColor3d(2,0,0)
                GL.glBegin(GL.GL_QUADS)
                GL.glVertex2d(xz-1, y+1)
                GL.glVertex2d(xz-1, y+14)
                GL.glVertex2d(xz+1, y+14)
                GL.glVertex2d(xz+1, y+1)
                GL.glEnd()
                GL.glColor3d(0,0,2)
                GL.glBegin(GL.GL_QUADS)
                GL.glVertex2d(x-1, y+1)
                GL.glVertex2d(x-1, y+14)
                GL.glVertex2d(x+1, y+14)
                GL.glVertex2d(x+1, y+1)
                GL.glEnd()
                GL.glColor3d(0,0,0)
                
                textPrefix = "||q[" + str(i) + "]|| = "
                if i < 10:
                    textPrefix = "||q[0" + str(i) + "]|| = "
                    
                self.clothScene.drawText(x=30, y=60.+18*i, text=textPrefix + '%.2f' % qlim[0], color=(0.,0,0))
                self.clothScene.drawText(x=x0, y=60.+18*i, text='%.3f' % self.robot_skeleton.q[i], color=(0.,0,0))
                self.clothScene.drawText(x=x1+2, y=60.+18*i, text='%.2f' % qlim[1], color=(0.,0,0))
        
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()
        a=0

    def inputFunc(self, repeat=False):
        pyutils.inputGenie(domain=self, repeat=repeat)

    def viewer_setup(self):
        self._get_viewer().scene.tb.trans[2] = -3.5
        self._get_viewer().scene.tb._set_theta(180)
        self._get_viewer().scene.tb._set_phi(180)
        self.track_skeleton_id = 0
        
def LERP(p0, p1, t):
    return p0 + (p1-p0)*t
