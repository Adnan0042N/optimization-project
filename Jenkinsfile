pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                echo 'Building application'
            }
        }

        stage('Test') {
            steps {
                echo 'Testing application'
            }
        }

        stage('Trigger Job-A') {
            steps {
                echo 'Job-A running'
                build job: 'firstPipelne'
            }
        }
    }
}
