pipeline {

    agent any

    parameters {
        choice(name: 'CUSTOMER', choices: ['customer1', 'customer2',], description: 'Customer name'),
        choice(name: 'ENVIRONMENT', choices: ['dev', 'staging'], description: 'Customer environemnt'),
        choice(name: 'AWS_REGION', choices: ['us-east-1', 'eu-west-1'], description: 'AWS region where customer environemnt is running (ie. EKS & RDS region)'),
        choice(name: 'EKS_CLUSTER', choices: ['cluster1', 'cluster2'], description: 'EKS cluster name where customer environemnt in running'),
        choice(name: 'ACTION', choices: ['get_env_state', 'up', 'down'], description: 'Action to perform on customer environemnt'),
        choice(name: 'S3_BUCKET_NAME', choices: ['customer-infra-manager'], description: 'S3 bucket for storing customer environemnt state'),
        choice(name: 'S3_REGION', choices: ['us-east-1'], description: 'S3 bucket region')
    }

    options {
        disableConcurrentBuilds()
        ansiColor('xterm')
    }

    stages {
        stage('Docker Build') {
            steps {
                sh 'docker build --network=host -t customer-infra-manager .'
            }
        }

        stage('Generate .env file') {
            steps {
                sh '''
                    cat <<EOF > params_${BUILD_NUMBER}.env
                    CUSTOMER=${CUSTOMER}
                    ENVIRONMENT=${ENVIRONMENT}
                    AWS_REGION=${AWS_REGION}
                    EKS_CLUSTER=${EKS_CLUSTER}
                    ACTION=${ACTION}
                    S3_BUCKET_NAME=${S3_BUCKET_NAME}
                    S3_REGION=${S3_REGION}
                    BUILD_NUMBER=${BUILD_NUMBER}
                    BUILD_USER=${BUILD_USER}
                    EOF
                '''
            }
        }

        stage('Docker Run and Sync') {
            steps {
                sh "docker run --name customer-infra-manager-${BUILD_NUMBER} --env-file=params_${BUILD_NUMBER}.env --rm customer-infra-manager"
            }
        }
    }

    post {
        always {
            sh "rm -f params_${BUILD_NUMBER}.env"
        }
    }
}