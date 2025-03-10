from datetime import datetime
from ammar_filter_post import get_posts_sorted_by_likes  # importing library
from boto3.dynamodb.conditions import Key

class DynamoDBUserManager:
    def __init__(self,DYNAMODB_TABLE_NAME, dynamodb):
        self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    def create_user(self, username, password, email):
        current_time = datetime.utcnow().isoformat()
        self.table.put_item(
            Item={
                'username': username,
                'password': password,
                'email': email,
                'created_at': current_time,
                'updated_at': current_time
            }
        )

    def delete_user(self, username):
        # Query to delete a user
        response = self.table.delete_item(
            Key={"username": username}, 
            ReturnValues="ALL_OLD"
        )

        return response
    def update_user(self, username, updates):
        """
        Dynamically update a user with the given `username`.
        """
        
        # Dynamically build UpdateExpression and ExpressionAttributeValues
        update_expression = "SET " + ", ".join([f"#{key} = :{key}" for key in updates.keys()])
        expression_attribute_values = {f":{key}": value for key, value in updates.items()}
        expression_attribute_names = {f"#{key}": key for key in updates.keys()}

        try:
            # Perform the update operation
            response = self.table.update_item(
                Key={
                    'username': username
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ExpressionAttributeNames=expression_attribute_names,
                ConditionExpression=Key('username').eq(username),  # Ensures only the owner can update
                ReturnValues="ALL_NEW"  # Return updated item
            )

            # Return the updated item
            return response
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            raise PermissionError("You are not authorized to update this user")
        except Exception as e:
            raise RuntimeError(f"An error occurred while updating the post: {str(e)}")
    
    def get_user(self, username):
        response = self.table.get_item(Key={'username': f"{username}"})
        return response.get('Item')

    def get_all_user(self):
        response = self.table.scan()
        users = response.get('Items', [])
        return users


class DynamoDBPostManager:
    def __init__(self,DYNAMODB_TABLE_NAME, dynamodb):
        self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    def create_post(self, post):
        self.table.put_item(Item=post)

    def get_post(self, username):
        response = self.table.get_item(Key={'username': f"{username}"})
        return response.get('Item')
    
    def get_post_by_post_id(self, post_id):
        response = self.table.query(
            KeyConditionExpression=Key('post_id').eq(post_id)
        )
        items = response.get('Items', [])
        return items[0] if items else None

    def get_all_post(self):
        response = self.table.scan()
        posts = response.get('Items', [])
        return posts
    def update_post(self, post_id, username, updates):
        """
        Dynamically update a post with the given `post_id` and `username`.
        """
        
        # Dynamically build UpdateExpression and ExpressionAttributeValues
        update_expression = "SET " + ", ".join([f"#{key} = :{key}" for key in updates.keys()])
        expression_attribute_values = {f":{key}": value for key, value in updates.items()}
        expression_attribute_names = {f"#{key}": key for key in updates.keys()}

        try:
            # Perform the update operation
            response = self.table.update_item(
                Key={
                    'post_id': post_id,
                    'username': username
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_attribute_values,
                ExpressionAttributeNames=expression_attribute_names,
                ConditionExpression=Key('username').eq(username),  # Ensures only the owner can update
                ReturnValues="ALL_NEW"  # Return updated item
            )

            # Return the updated item
            return response.get('Attributes', {})

        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            raise PermissionError("You are not authorized to update this post")
        except Exception as e:
            raise RuntimeError(f"An error occurred while updating the post: {str(e)}")

    def delete_post(self, post_id, username):
        # Delete post from DynamoDB
        response = self.table.delete_item(
            Key={
                'post_id': post_id,  
                'username': username  
            },
            ReturnValues="ALL_OLD"
        )
        return response
    
    def update_post_like_count(self, post_id,username, increment):
        post_data = self.table.get_item(Key={'post_id': f"{post_id}" , 'username': username}).get('Item')
        updated_at = datetime.utcnow().isoformat()
        if increment:
            # Increment likes in DynamoDB
            response = self.table.update_item(
                        Key={
                            'post_id': post_data['post_id'],
                            'username': post_data['username'], 
                        },
                        UpdateExpression="""
                            SET caption = :caption,
                                comments_count =:comments_count,
                                created_at =:created_at,
                                image_url =:image_url,
                                updated_at =:updated_at,
                            
                                likes_count = if_not_exists(likes_count, :start) + :inc
                            """,
                        ExpressionAttributeValues={
                            ':caption': post_data['caption'],
                            ':comments_count': post_data['comments_count'],
                            ':created_at': post_data['created_at'],
                            ':image_url': post_data['image_url'],
                            ':updated_at': updated_at,
                            ':inc': 1,
                            ':start': 0
                    },
                    ReturnValues="UPDATED_NEW"
            )
        else:

            # Increment likes in DynamoDB
            response = self.table.update_item(
                        Key={
                            'post_id': post_data['post_id'],
                            'username': post_data['username'] 
                        },
                        UpdateExpression="""
                            SET caption = :caption,
                                comments_count =:comments_count,
                                created_at =:created_at,
                                image_url =:image_url,
                                updated_at =:updated_at,
                            
                                likes_count = if_not_exists(likes_count, :start) + :inc
                            """,
                        ExpressionAttributeValues={
                            ':caption': post_data['caption'],
                            ':comments_count': post_data['comments_count'],
                            ':created_at': post_data['created_at'],
                            ':image_url': post_data['image_url'],
                            ':updated_at': updated_at,
                            ':inc': -1,
                            ':start': 0
                    },
                    ReturnValues="UPDATED_NEW"
            )
        return response
    
    def update_post_comment_count(self, post_id, username):
        post_data = self.table.get_item(Key={'post_id': f"{post_id}" , 'username': username}).get('Item')
        print(f"POST_DATA: {post_data}")
        updated_at = datetime.utcnow().isoformat()
        response = self.table.update_item(
                        Key={
                            'post_id': post_data['post_id'],
                            'username': post_data['username'] 
                        },
                        UpdateExpression="""
                            SET caption = :caption,
                                likes_count =:likes_count,
                                created_at =:created_at,
                                image_url =:image_url,
                                updated_at =:updated_at, 
                                comments_count = if_not_exists(comments_count, :start) + :inc
                            """,
                        ExpressionAttributeValues={
                            ':caption': post_data['caption'],
                            ':likes_count': post_data['likes_count'],
                            ':created_at': post_data['created_at'],
                            ':image_url': post_data['image_url'],
                            ':updated_at': updated_at,
                            ':inc': 1,
                            ':start': 0
                    },
                    ReturnValues="UPDATED_NEW"
            )

        return response
    
    def filter_all_post_by_likes(self):
        
        sorted_posts = get_posts_sorted_by_likes(self.table)

        return sorted_posts

class DynamoDBLikeManager:
    def __init__(self,DYNAMODB_TABLE_NAME, dynamodb):
        self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    def add_like(self, like_data):
        response = self.table.put_item(
                Item=like_data,
                ConditionExpression="attribute_not_exists(post_id) AND attribute_not_exists(username)"
            )
        return response
     
    def get_all_likes_by_post(self, post_id):
        response = self.table.query(
            KeyConditionExpression=Key('post_id').eq(post_id)
        )
        items = response.get('Items', [])
        return items

    
    
    def delete_like_by_post_id(self, post_id, username):
        # Delete post from DynamoDB
        response = self.table.delete_item(
            Key={
                'post_id': post_id,       # Replace with the actual post_id
                'username': username      # Replace with the actual username
            },
            ReturnValues="ALL_OLD"
        )
        return response


class DynamoDBCommentManager:
    def __init__(self,DYNAMODB_TABLE_NAME, dynamodb):
        self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
    
    def add_comment(self, comment_data):

        comment_id = comment_data['comment_id']
        created_at = comment_data['created_at']
        content = [comment_data['content']]
        username = comment_data['username']
        post_id = comment_data['post_id']
        # Update the item in DynamoDB
        response = self.table.update_item(
            Key={'post_id': post_id, 'username': username},
            UpdateExpression="""
                SET created_at = :created_at,
                    comment_id = :comment_id,
                    content = list_append(if_not_exists(content, :empty_list), :new_content)
                """,
            ExpressionAttributeValues={
                ':created_at': created_at,
                ':comment_id': comment_id,
                ':new_content': content,
                ':empty_list': []
            },
            ReturnValues="UPDATED_NEW"
        )
        
        return response
    
    def get_all_comments(self):
        response = self.table.scan()
        comments = response.get('Items', [])
        return comments
    
    def delete_comments_by_post_id(self, post_id, username):
        # Delete post from DynamoDB
        response = self.table.delete_item(
            Key={
                'post_id': post_id,  
                'username': username  
            },
            ReturnValues="ALL_OLD"
        )
        return response
    