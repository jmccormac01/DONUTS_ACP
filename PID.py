"""
PID loop controller
"""

# pylint: disable=invalid-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes

class PID:
    """
    Discrete PID control

    http://code.activestate.com/recipes/577231-discrete-pid-controller/
    """
    def __init__(self, P=0.5, I=0.25, D=0.0, Derivator=0,
                 Integrator=0, Integrator_max=500, Integrator_min=-500):
        self.Kp = P
        self.Ki = I
        self.Kd = D
        self.Derivator = Derivator
        self.Integrator = Integrator
        self.Integrator_max = Integrator_max
        self.Integrator_min = Integrator_min
        self.set_point = 0.0
        self.error = 0.0
        self.P_value = 0.0 # included as pylint complained - jmcc
        self.D_value = 0.0 # included as pylint complained - jmcc
        self.I_value = 0.0 # included as pylint complained - jmcc

    def update(self, current_value):
        """
        Calculate PID output value for given reference input and feedback
        """
        self.error = self.set_point - current_value
        self.P_value = self.Kp * self.error
        self.D_value = self.Kd * (self.error - self.Derivator)
        self.Derivator = self.error
        self.Integrator = self.Integrator + self.error
        if self.Integrator > self.Integrator_max:
            self.Integrator = self.Integrator_max
        elif self.Integrator < self.Integrator_min:
            self.Integrator = self.Integrator_min
        self.I_value = self.Integrator * self.Ki
        pid = self.P_value + self.I_value + self.D_value
        return pid
    def setPoint(self, set_point):
        """
        Initilize the setpoint of PID
        """
        self.set_point = set_point
        self.Integrator = 0
        self.Derivator = 0
    def setIntegrator(self, Integrator):
        """
        Set Integrator
        """
        self.Integrator = Integrator
    def setDerivator(self, Derivator):
        """
        Set Derivator
        """
        self.Derivator = Derivator
    def setKp(self, P):
        """
        Set Kp
        """
        self.Kp = P
    def setKi(self, I):
        """
        Set Ki
        """
        self.Ki = I
    def setKd(self, D):
        """
        Set Kd
        """
        self.Kd = D
    def getPoint(self):
        """
        Get point
        """
        return self.set_point
    def getError(self):
        """
        Get Error
        """
        return self.error
    def getIntegrator(self):
        """
        Get Integrator
        """
        return self.Integrator
    def getDerivator(self):
        """
        Get Derivator
        """
        return self.Derivator
