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
    }
    pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Job-A running'
            }
        }
    }
    post {
        success {
            build job: 'firstPipelne'
        }
    }
}

    }
